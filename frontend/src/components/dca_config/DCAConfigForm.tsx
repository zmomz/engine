
import React, { useEffect, useState } from 'react';
import {
    Button,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Grid,
    TextField,
    MenuItem,
    IconButton,
    Typography,
    Paper,
    Alert,
    Tabs,
    Tab,
    Box,
    FormControlLabel,
    Checkbox,
    useTheme,
    useMediaQuery
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useForm, useFieldArray, Controller, Control, UseFormWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { DCAConfiguration } from '../../api/dcaConfig';
import { safeToFixed } from '../../utils/formatters';

// Schemas
const dcaLevelSchema = z.object({
    gap_percent: z.coerce.number(),
    weight_percent: z.coerce.number().gt(0, "Weight > 0"),
    tp_percent: z.coerce.number().gt(0, "TP > 0"),
});

const formSchema = z.object({
    pair: z.string().min(1, "Pair is required"),
    timeframe: z.coerce.number().min(1, "Timeframe must be at least 1 minute"),
    exchange: z.string().min(1, "Exchange is required"),
    entry_order_type: z.enum(["limit", "market"]),
    dca_levels: z.array(dcaLevelSchema).superRefine((data, ctx) => {
        const totalWeight = data.reduce((sum, item) => sum + item.weight_percent, 0);
        if (Math.abs(totalWeight - 100) > 0.01) {
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                message: `Total weight must be 100% (Current: ${safeToFixed(totalWeight)}%)`,
                path: []
            });
        }
    }),
    pyramid_specific_levels: z.record(z.string(), z.array(dcaLevelSchema)).optional(),
    tp_mode: z.enum(["per_leg", "aggregate", "hybrid", "pyramid_aggregate"]),
    tp_settings: z.object({
        tp_aggregate_percent: z.coerce.number().optional(),
        pyramid_tp_percents: z.record(z.string(), z.coerce.number()).optional()
    }),
    max_pyramids: z.coerce.number().min(1)
});

type FormValues = z.infer<typeof formSchema>;

interface DCAConfigFormProps {
    open: boolean;
    onClose: () => void;
    onSubmit: (data: FormValues) => Promise<void>;
    initialData?: DCAConfiguration; // Using the API type which now includes pyramid_specific_levels
    isEdit?: boolean;
}

// Sub-component for editing levels
const DCALevelsEditor: React.FC<{
    control: Control<FormValues>,
    name: any, // Path to the array field
    tpMode: string,
    watch: UseFormWatch<FormValues>
}> = ({ control, name, tpMode, watch }) => {
    const { fields, append, remove } = useFieldArray({
        control,
        name: name
    });

    return (
        <Box>
            {fields.map((field, index) => (
                <Paper key={field.id} variant="outlined" sx={{ p: { xs: 1, sm: 2 }, mb: 1 }}>
                    <Grid container spacing={{ xs: 1, sm: 2 }} alignItems="center">
                        <Grid size={{ xs: 2, sm: 1 }}>
                            <Typography sx={{ fontSize: { xs: '0.75rem', sm: '1rem' } }}>#{index}</Typography>
                        </Grid>
                        <Grid size={{ xs: 10, sm: 3 }}>
                            <Controller
                                name={`${name}.${index}.gap_percent` as any}
                                control={control}
                                render={({ field }) => <TextField {...field} label="Gap %" size="small" type="number" fullWidth />}
                            />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 3 }}>
                            <Controller
                                name={`${name}.${index}.weight_percent` as any}
                                control={control}
                                render={({ field }) => <TextField {...field} label="Weight %" size="small" type="number" fullWidth />}
                            />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 3 }}>
                            <Controller
                                name={`${name}.${index}.tp_percent` as any}
                                control={control}
                                render={({ field }) => <TextField {...field} label="TP %" size="small" type="number" fullWidth disabled={tpMode === 'aggregate' || tpMode === 'pyramid_aggregate'} />}
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 2 }} sx={{ display: 'flex', justifyContent: { xs: 'flex-end', sm: 'center' } }}>
                            <IconButton color="error" onClick={() => remove(index)} size="small">
                                <DeleteIcon sx={{ fontSize: { xs: 18, sm: 24 } }} />
                            </IconButton>
                        </Grid>
                    </Grid>
                </Paper>
            ))}

            <Button variant="outlined" onClick={() => append({ gap_percent: 1, weight_percent: 0, tp_percent: 1 })} sx={{ mt: 1 }} size="small">
                Add Level
            </Button>
        </Box>
    );
};

const DCAConfigForm: React.FC<DCAConfigFormProps> = ({ open, onClose, onSubmit, initialData, isEdit }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const { control, handleSubmit, reset, watch, setValue, formState: { errors, isSubmitting } } = useForm<FormValues>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            pair: '',
            timeframe: 60,
            exchange: 'binance',
            entry_order_type: 'limit',
            dca_levels: [],
            pyramid_specific_levels: {},
            tp_mode: 'per_leg',
            tp_settings: { tp_aggregate_percent: 0, pyramid_tp_percents: {} },
            max_pyramids: 5
        }
    });

    const [tabIndex, setTabIndex] = useState(0); // 0 = Default, 1..N = Pyramid Index (mapped visually)

    const tpMode = watch("tp_mode");
    const maxPyramids = watch("max_pyramids") || 5;
    const pyramidSpecifics = watch("pyramid_specific_levels") || {};
    const pyramidTpPercents = watch("tp_settings.pyramid_tp_percents") || {};

    useEffect(() => {
        if (open) {
            if (initialData) {
                reset({
                    pair: initialData.pair,
                    timeframe: initialData.timeframe,
                    exchange: initialData.exchange,
                    entry_order_type: initialData.entry_order_type,
                    dca_levels: initialData.dca_levels,
                    pyramid_specific_levels: initialData.pyramid_specific_levels || {},
                    tp_mode: initialData.tp_mode,
                    tp_settings: {
                        tp_aggregate_percent: initialData.tp_settings?.tp_aggregate_percent || 0,
                        pyramid_tp_percents: initialData.tp_settings?.pyramid_tp_percents || {}
                    },
                    max_pyramids: initialData.max_pyramids
                });
            } else {
                reset({
                    pair: '',
                    timeframe: 60,
                    exchange: 'binance',
                    entry_order_type: 'limit',
                    dca_levels: [],
                    pyramid_specific_levels: {},
                    tp_mode: 'per_leg',
                    tp_settings: { tp_aggregate_percent: 0, pyramid_tp_percents: {} },
                    max_pyramids: 5
                });
            }
            setTabIndex(0);
        }
    }, [open, initialData, reset]);

    const handlePyramidTpChange = (pyramidIdx: string, value: number | null) => {
        const current = { ...(watch("tp_settings.pyramid_tp_percents") || {}) };
        if (value === null || value === 0) {
            delete current[pyramidIdx];
        } else {
            current[pyramidIdx] = value;
        }
        setValue("tp_settings.pyramid_tp_percents", current);
    };

    const handleFormSubmit = async (data: FormValues) => {
        // Map flat settings back to tp_settings dict if needed, handled by schema/form structure
        await onSubmit(data);
        onClose();
    };

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTabIndex(newValue);
    };

    const handleTogglePyramidOverride = (pyramidIdx: string, checked: boolean) => {
        const current = { ...watch("pyramid_specific_levels") };
        if (checked) {
            // Initialize with copy of default or empty
            current[pyramidIdx] = [...watch("dca_levels")];
        } else {
            delete current[pyramidIdx];
        }
        setValue("pyramid_specific_levels", current);
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth fullScreen={isMobile}>
            <DialogTitle sx={{ fontSize: { xs: '1rem', sm: '1.25rem' }, py: { xs: 1.5, sm: 2 } }}>
                {isEdit ? 'Edit DCA Configuration' : 'Create DCA Configuration'}
            </DialogTitle>
            <form onSubmit={handleSubmit(handleFormSubmit)}>
                <DialogContent dividers sx={{ p: { xs: 1.5, sm: 3 } }}>
                    <Grid container spacing={{ xs: 1.5, sm: 2 }}>
                        {/* Basic Info */}
                        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                            <Controller
                                name="pair"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} label="Pair" size="small" fullWidth error={!!errors.pair} helperText={errors.pair?.message} disabled={isEdit} placeholder="BTC/USDT" />
                                )}
                            />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 6, md: 4 }}>
                            <Controller
                                name="timeframe"
                                control={control}
                                render={({ field }) => (
                                    <TextField
                                        {...field}
                                        label="TF (min)"
                                        type="number"
                                        size="small"
                                        fullWidth
                                        error={!!errors.timeframe}
                                        helperText={errors.timeframe?.message}
                                        disabled={isEdit}
                                        inputProps={{ min: 1, step: 1 }}
                                    />
                                )}
                            />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 6, md: 4 }}>
                            <Controller
                                name="exchange"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} label="Exchange" size="small" fullWidth error={!!errors.exchange} disabled={isEdit} />
                                )}
                            />
                        </Grid>

                        <Grid size={{ xs: 6, sm: 6 }}>
                            <Controller
                                name="entry_order_type"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} select label="Entry Type" size="small" fullWidth>
                                        <MenuItem value="limit">Limit</MenuItem>
                                        <MenuItem value="market">Market</MenuItem>
                                    </TextField>
                                )}
                            />
                        </Grid>
                        <Grid size={{ xs: 6, sm: 6 }}>
                            <Controller
                                name="max_pyramids"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} type="number" label="Max Pyramids" size="small" fullWidth error={!!errors.max_pyramids} />
                                )}
                            />
                        </Grid>

                        {/* TP Settings */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" sx={{ mt: 1, fontWeight: 600 }}>Take Profit</Typography>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                            <Controller
                                name="tp_mode"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} select label="TP Mode" size="small" fullWidth>
                                        <MenuItem value="per_leg">Per Leg</MenuItem>
                                        <MenuItem value="aggregate">Aggregate</MenuItem>
                                        <MenuItem value="hybrid">Hybrid</MenuItem>
                                        <MenuItem value="pyramid_aggregate">Pyr Aggregate</MenuItem>
                                    </TextField>
                                )}
                            />
                        </Grid>

                        {(tpMode === 'aggregate' || tpMode === 'hybrid' || tpMode === 'pyramid_aggregate') && (
                            <Grid size={{ xs: 6 }}>
                                <Controller
                                    name="tp_settings.tp_aggregate_percent"
                                    control={control}
                                    render={({ field }) => (
                                        <TextField {...field} type="number" label="Agg TP %" size="small" fullWidth inputProps={{ step: "0.01" }} />
                                    )}
                                />
                            </Grid>
                        )}


                        {/* Levels Tabs */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle2" sx={{ mt: 1, fontWeight: 600 }}>DCA Levels</Typography>
                            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                                <Tabs
                                    value={tabIndex}
                                    onChange={handleTabChange}
                                    variant="scrollable"
                                    scrollButtons="auto"
                                    sx={{
                                        minHeight: { xs: 36, sm: 48 },
                                        '& .MuiTab-root': {
                                            minHeight: { xs: 36, sm: 48 },
                                            fontSize: { xs: '0.7rem', sm: '0.875rem' },
                                            px: { xs: 1, sm: 2 }
                                        }
                                    }}
                                >
                                    <Tab label="Default" />
                                    {Array.from({ length: maxPyramids }, (_, i) => i + 1).map((idx) => (
                                        <Tab
                                            key={idx}
                                            label={
                                                <Box display="flex" alignItems="center">
                                                    {`P${idx}`}
                                                    {pyramidSpecifics && pyramidSpecifics[idx.toString()] && (
                                                        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'primary.main', ml: 0.5 }} />
                                                    )}
                                                </Box>
                                            }
                                        />
                                    ))}
                                </Tabs>
                            </Box>

                            <Box sx={{ p: { xs: 1, sm: 2 }, minHeight: { xs: 200, sm: 300 } }}>
                                {tabIndex === 0 ? (
                                    <Box>
                                        <Alert severity="info" sx={{ mb: 2, py: 0.5, '& .MuiAlert-message': { fontSize: { xs: '0.7rem', sm: '0.875rem' } } }}>
                                            Default levels for initial position (P0) and pyramids without overrides.
                                        </Alert>

                                        {/* P0 TP % override for pyramid_aggregate mode */}
                                        {tpMode === 'pyramid_aggregate' && (
                                            <Box sx={{ mb: 2 }}>
                                                <TextField
                                                    type="number"
                                                    label="P0 TP % (Initial Entry)"
                                                    size="small"
                                                    value={pyramidTpPercents["0"] || ''}
                                                    onChange={(e) => handlePyramidTpChange(
                                                        "0",
                                                        e.target.value ? parseFloat(e.target.value) : null
                                                    )}
                                                    placeholder={`Default: ${watch("tp_settings.tp_aggregate_percent") || 0}%`}
                                                    inputProps={{ step: "0.01" }}
                                                    sx={{ width: { xs: '100%', sm: 200 } }}
                                                    helperText="Leave empty to use default Agg TP %"
                                                />
                                            </Box>
                                        )}

                                        {errors.dca_levels && (
                                            <Alert severity="error" sx={{ mb: 2, py: 0.5 }}>{(errors.dca_levels as any).root?.message || "Invalid levels"}</Alert>
                                        )}
                                        <DCALevelsEditor control={control} name="dca_levels" tpMode={tpMode} watch={watch} />
                                    </Box>
                                ) : (
                                    <Box>
                                        <Alert severity="info" sx={{ mb: 2, py: 0.5, '& .MuiAlert-message': { fontSize: { xs: '0.7rem', sm: '0.875rem' } } }}>
                                            Pyramid {tabIndex} config (only if enabled).
                                        </Alert>

                                        {/* Per-Pyramid TP % for pyramid_aggregate mode */}
                                        {tpMode === 'pyramid_aggregate' && (
                                            <Box sx={{ mb: 2 }}>
                                                <TextField
                                                    type="number"
                                                    label={`P${tabIndex} TP %`}
                                                    size="small"
                                                    value={pyramidTpPercents[tabIndex.toString()] || ''}
                                                    onChange={(e) => handlePyramidTpChange(
                                                        tabIndex.toString(),
                                                        e.target.value ? parseFloat(e.target.value) : null
                                                    )}
                                                    placeholder={`Default: ${watch("tp_settings.tp_aggregate_percent") || 0}%`}
                                                    inputProps={{ step: "0.01" }}
                                                    sx={{ width: { xs: '100%', sm: 200 } }}
                                                    helperText="Leave empty to use default Agg TP %"
                                                />
                                            </Box>
                                        )}

                                        <FormControlLabel
                                            control={
                                                <Checkbox
                                                    checked={!!(pyramidSpecifics && pyramidSpecifics[tabIndex.toString()])}
                                                    onChange={(e) => handleTogglePyramidOverride(tabIndex.toString(), e.target.checked)}
                                                    size="small"
                                                />
                                            }
                                            label={<Box component="span" sx={{ fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>Enable P{tabIndex} DCA levels</Box>}
                                        />

                                        {pyramidSpecifics && pyramidSpecifics[tabIndex.toString()] && (
                                            <Box sx={{ mt: 2 }}>
                                                <DCALevelsEditor control={control} name={`pyramid_specific_levels.${tabIndex.toString()}`} tpMode={tpMode} watch={watch} />
                                            </Box>
                                        )}
                                    </Box>
                                )}
                            </Box>
                        </Grid>

                    </Grid>
                </DialogContent>
                <DialogActions sx={{ p: { xs: 1.5, sm: 2 } }}>
                    <Button onClick={onClose} size="small">Cancel</Button>
                    <Button type="submit" variant="contained" disabled={isSubmitting} size="small">Save</Button>
                </DialogActions>
            </form>
        </Dialog>
    );
};

export default DCAConfigForm;
