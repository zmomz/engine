
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
    Checkbox
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { useForm, useFieldArray, Controller, Control, UseFormWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { DCAConfiguration } from '../../api/dcaConfig';

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
                message: `Total weight must be 100% (Current: ${totalWeight.toFixed(2)}%)`,
                path: []
            });
        }
    }),
    pyramid_specific_levels: z.record(z.string(), z.array(dcaLevelSchema)).optional(),
    tp_mode: z.enum(["per_leg", "aggregate", "hybrid", "pyramid_aggregate"]),
    tp_settings: z.object({
        tp_aggregate_percent: z.coerce.number().optional()
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
                <Paper key={field.id} variant="outlined" sx={{ p: 2, mb: 1 }}>
                    <Grid container spacing={2} alignItems="center">
                        <Grid size={{ xs: 1 }}>
                            <Typography>#{index}</Typography>
                        </Grid>
                        <Grid size={{ xs: 3 }}>
                            <Controller
                                name={`${name}.${index}.gap_percent` as any}
                                control={control}
                                render={({ field }) => <TextField {...field} label="Gap %" size="small" type="number" fullWidth />}
                            />
                        </Grid>
                        <Grid size={{ xs: 3 }}>
                            <Controller
                                name={`${name}.${index}.weight_percent` as any}
                                control={control}
                                render={({ field }) => <TextField {...field} label="Weight %" size="small" type="number" fullWidth />}
                            />
                        </Grid>
                        <Grid size={{ xs: 3 }}>
                            <Controller
                                name={`${name}.${index}.tp_percent` as any}
                                control={control}
                                render={({ field }) => <TextField {...field} label="TP %" size="small" type="number" fullWidth disabled={tpMode === 'aggregate' || tpMode === 'pyramid_aggregate'} />}
                            />
                        </Grid>
                        <Grid size={{ xs: 2 }}>
                            <IconButton color="error" onClick={() => remove(index)}>
                                <DeleteIcon />
                            </IconButton>
                        </Grid>
                    </Grid>
                </Paper>
            ))}

            <Button variant="outlined" onClick={() => append({ gap_percent: 1, weight_percent: 0, tp_percent: 1 })} sx={{ mt: 1 }}>
                Add Level
            </Button>
        </Box>
    );
};

const DCAConfigForm: React.FC<DCAConfigFormProps> = ({ open, onClose, onSubmit, initialData, isEdit }) => {
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
            tp_settings: { tp_aggregate_percent: 0 },
            max_pyramids: 5
        }
    });

    const [tabIndex, setTabIndex] = useState(0); // 0 = Default, 1..N = Pyramid Index (mapped visually)

    const tpMode = watch("tp_mode");
    const maxPyramids = watch("max_pyramids") || 5;
    const pyramidSpecifics = watch("pyramid_specific_levels") || {};

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
                        tp_aggregate_percent: initialData.tp_settings?.tp_aggregate_percent || 0
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
                    tp_settings: { tp_aggregate_percent: 0 },
                    max_pyramids: 5
                });
            }
            setTabIndex(0);
        }
    }, [open, initialData, reset]);

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
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>{isEdit ? 'Edit DCA Configuration' : 'Create DCA Configuration'}</DialogTitle>
            <form onSubmit={handleSubmit(handleFormSubmit)}>
                <DialogContent dividers>
                    <Grid container spacing={2}>
                        {/* Basic Info */}
                        <Grid size={{ xs: 12, md: 4 }}>
                            <Controller
                                name="pair"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} label="Pair (e.g. BTC/USDT)" fullWidth error={!!errors.pair} helperText={errors.pair?.message} disabled={isEdit} />
                                )}
                            />
                        </Grid>
                        <Grid size={{ xs: 12, md: 4 }}>
                            <Controller
                                name="timeframe"
                                control={control}
                                render={({ field }) => (
                                    <TextField
                                        {...field}
                                        label="Timeframe (minutes)"
                                        type="number"
                                        fullWidth
                                        error={!!errors.timeframe}
                                        helperText={errors.timeframe?.message}
                                        disabled={isEdit}
                                        inputProps={{ min: 1, step: 1 }}
                                    />
                                )}
                            />
                        </Grid>
                        <Grid size={{ xs: 12, md: 4 }}>
                            <Controller
                                name="exchange"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} label="Exchange" fullWidth error={!!errors.exchange} disabled={isEdit} />
                                )}
                            />
                        </Grid>

                        <Grid size={{ xs: 12, md: 6 }}>
                            <Controller
                                name="entry_order_type"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} select label="Entry Order Type" fullWidth>
                                        <MenuItem value="limit">Limit</MenuItem>
                                        <MenuItem value="market">Market (Watch Price)</MenuItem>
                                    </TextField>
                                )}
                            />
                        </Grid>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Controller
                                name="max_pyramids"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} type="number" label="Max Pyramids" fullWidth error={!!errors.max_pyramids} />
                                )}
                            />
                        </Grid>

                        {/* TP Settings */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle1" sx={{ mt: 2 }}>Take Profit Strategy</Typography>
                        </Grid>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Controller
                                name="tp_mode"
                                control={control}
                                render={({ field }) => (
                                    <TextField {...field} select label="TP Mode" fullWidth>
                                        <MenuItem value="per_leg">Per Leg</MenuItem>
                                        <MenuItem value="aggregate">Aggregate</MenuItem>
                                        <MenuItem value="hybrid">Hybrid</MenuItem>
                                        <MenuItem value="pyramid_aggregate">Pyramid Aggregate</MenuItem>
                                    </TextField>
                                )}
                            />
                        </Grid>

                        {(tpMode === 'aggregate' || tpMode === 'hybrid' || tpMode === 'pyramid_aggregate') && (
                            <Grid size={{ xs: 12, md: 6 }}>
                                <Controller
                                    name="tp_settings.tp_aggregate_percent"
                                    control={control}
                                    render={({ field }) => (
                                        <TextField {...field} type="number" label="Aggregate TP %" fullWidth inputProps={{ step: "0.01" }} />
                                    )}
                                />
                            </Grid>
                        )}


                        {/* Levels Tabs */}
                        <Grid size={{ xs: 12 }}>
                            <Typography variant="subtitle1" sx={{ mt: 2 }}>DCA Levels Configuration</Typography>
                            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                                <Tabs value={tabIndex} onChange={handleTabChange} variant="scrollable" scrollButtons="auto">
                                    <Tab label="Default (Base)" />
                                    {Array.from({ length: maxPyramids }, (_, i) => i + 1).map((idx) => (
                                        <Tab
                                            key={idx}
                                            label={
                                                <Box display="flex" alignItems="center">
                                                    {`Pyramid ${idx}`}
                                                    {pyramidSpecifics && pyramidSpecifics[idx.toString()] && (
                                                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: 'primary.main', ml: 1 }} />
                                                    )}
                                                </Box>
                                            }
                                        />
                                    ))}
                                </Tabs>
                            </Box>

                            <Box sx={{ p: 2, minHeight: 300 }}>
                                {tabIndex === 0 ? (
                                    <Box>
                                        <Alert severity="info" sx={{ mb: 2 }}>These levels apply to the INITIAL position and any subsequent pyramids that do not have specific overrides.</Alert>
                                        {errors.dca_levels && (
                                            <Alert severity="error" sx={{ mb: 2 }}>{(errors.dca_levels as any).root?.message || "Invalid levels configuration"}</Alert>
                                        )}
                                        <DCALevelsEditor control={control} name="dca_levels" tpMode={tpMode} watch={watch} />
                                    </Box>
                                ) : (
                                    <Box>
                                        <Alert severity="info" sx={{ mb: 2 }}>Configuration for Pyramid {tabIndex}. Only used if enabled.</Alert>
                                        <FormControlLabel
                                            control={
                                                <Checkbox
                                                    checked={!!(pyramidSpecifics && pyramidSpecifics[tabIndex.toString()])}
                                                    onChange={(e) => handleTogglePyramidOverride(tabIndex.toString(), e.target.checked)}
                                                />
                                            }
                                            label={`Enable Specific Settings for Pyramid ${tabIndex}`}
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
                <DialogActions>
                    <Button onClick={onClose}>Cancel</Button>
                    <Button type="submit" variant="contained" disabled={isSubmitting}>Save Configuration</Button>
                </DialogActions>
            </form>
        </Dialog>
    );
};

export default DCAConfigForm;
