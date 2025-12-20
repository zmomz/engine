
import React, { useEffect, useState } from 'react';
import {
    Box,
    Button,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    IconButton,
    Typography,
    Chip,
    CircularProgress,
    Alert
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { dcaConfigApi, DCAConfiguration } from '../../api/dcaConfig'; // Ensure this matches filename
import DCAConfigForm from './DCAConfigForm';

const DCAConfigList: React.FC = () => {
    const [configs, setConfigs] = useState<DCAConfiguration[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [selectedConfig, setSelectedConfig] = useState<DCAConfiguration | undefined>(undefined);

    const fetchConfigs = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await dcaConfigApi.getAll();
            setConfigs(data);
        } catch (err) {
            console.error(err);
            setError("Failed to load configurations");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchConfigs();
    }, []);

    const handleCreate = () => {
        setSelectedConfig(undefined);
        setIsFormOpen(true);
    };

    const handleEdit = (config: DCAConfiguration) => {
        setSelectedConfig(config);
        setIsFormOpen(true);
    };

    const handleDelete = async (id: string) => {
        if (window.confirm("Are you sure you want to delete this configuration?")) {
            try {
                await dcaConfigApi.delete(id);
                fetchConfigs();
            } catch (err) {
                console.error(err);
                alert("Failed to delete configuration");
            }
        }
    };

    const handleFormSubmit = async (data: any) => {
        try {
            if (selectedConfig) {
                await dcaConfigApi.update(selectedConfig.id, data);
            } else {
                await dcaConfigApi.create(data);
            }
            fetchConfigs();
        } catch (err: any) {
            console.error(err);
            alert(`Failed to save: ${err.response?.data?.detail || err.message}`);
            // Re-throw to keep form open? Form implementation closes on submit but maybe we should wait.
            // Current form implementation closes on submit automatically which is generic.
            // Ideally we pass error back to form.
        }
    };

    return (
        <Box>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2} flexWrap="wrap" gap={1}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: { xs: '0.95rem', sm: '1.1rem' } }}>
                    Specific DCA Configurations
                </Typography>
                <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate} size="small">
                    Add
                </Button>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {loading ? (
                <CircularProgress />
            ) : (
                <TableContainer component={Paper} variant="outlined" sx={{ maxWidth: '100%', overflowX: 'auto' }}>
                    <Table size="small" sx={{ minWidth: { xs: 320, sm: 500 } }}>
                        <TableHead>
                            <TableRow>
                                <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 1, sm: 2 } }}>Pair</TableCell>
                                <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 }, display: { xs: 'none', sm: 'table-cell' } }}>TF</TableCell>
                                <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 }, display: { xs: 'none', sm: 'table-cell' } }}>Exchange</TableCell>
                                <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 } }}>Entry</TableCell>
                                <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 } }}>TP</TableCell>
                                <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 } }}>Pyr</TableCell>
                                <TableCell align="right" sx={{ px: { xs: 0.5, sm: 2 } }}>Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {configs.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} align="center" sx={{ fontSize: '0.8rem' }}>No configs found</TableCell>
                                </TableRow>
                            ) : (
                                configs.map((config) => (
                                    <TableRow key={config.id}>
                                        <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 1, sm: 2 } }}>{config.pair}</TableCell>
                                        <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 }, display: { xs: 'none', sm: 'table-cell' } }}>{config.timeframe}</TableCell>
                                        <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 }, display: { xs: 'none', sm: 'table-cell' } }}>{config.exchange}</TableCell>
                                        <TableCell sx={{ px: { xs: 0.5, sm: 2 } }}>
                                            <Chip label={config.entry_order_type === 'market' ? 'M' : 'L'} size="small" color={config.entry_order_type === 'market' ? 'warning' : 'default'} sx={{ height: 20, fontSize: '0.65rem' }} />
                                        </TableCell>
                                        <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 } }}>{config.tp_mode}</TableCell>
                                        <TableCell sx={{ fontSize: { xs: '0.7rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 } }}>{config.max_pyramids}</TableCell>
                                        <TableCell align="right" sx={{ px: { xs: 0.5, sm: 2 }, whiteSpace: 'nowrap' }}>
                                            <IconButton size="small" onClick={() => handleEdit(config)} sx={{ p: { xs: 0.25, sm: 0.5 } }}>
                                                <EditIcon sx={{ fontSize: { xs: 16, sm: 20 } }} />
                                            </IconButton>
                                            <IconButton size="small" color="error" onClick={() => handleDelete(config.id)} sx={{ p: { xs: 0.25, sm: 0.5 } }}>
                                                <DeleteIcon sx={{ fontSize: { xs: 16, sm: 20 } }} />
                                            </IconButton>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}

            <DCAConfigForm
                open={isFormOpen}
                onClose={() => setIsFormOpen(false)}
                onSubmit={handleFormSubmit}
                initialData={selectedConfig}
                isEdit={!!selectedConfig}
            />
        </Box>
    );
};

export default DCAConfigList;
