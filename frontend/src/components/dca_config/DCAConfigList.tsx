
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
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">Specific DCA Configurations</Typography>
                <Button variant="contained" startIcon={<AddIcon />} onClick={handleCreate} size="small">
                    Add New Config
                </Button>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {loading ? (
                <CircularProgress />
            ) : (
                <TableContainer component={Paper} variant="outlined">
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Pair</TableCell>
                                <TableCell>Timeframe</TableCell>
                                <TableCell>Exchange</TableCell>
                                <TableCell>Entry</TableCell>
                                <TableCell>TP Mode</TableCell>
                                <TableCell>Pyramids</TableCell>
                                <TableCell align="right">Actions</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {configs.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={7} align="center">No specific configurations found.</TableCell>
                                </TableRow>
                            ) : (
                                configs.map((config) => (
                                    <TableRow key={config.id}>
                                        <TableCell>{config.pair}</TableCell>
                                        <TableCell>{config.timeframe}</TableCell>
                                        <TableCell>{config.exchange}</TableCell>
                                        <TableCell>
                                            <Chip label={config.entry_order_type} size="small" color={config.entry_order_type === 'market' ? 'warning' : 'default'} />
                                        </TableCell>
                                        <TableCell>{config.tp_mode}</TableCell>
                                        <TableCell>{config.max_pyramids}</TableCell>
                                        <TableCell align="right">
                                            <IconButton size="small" onClick={() => handleEdit(config)}>
                                                <EditIcon fontSize="small" />
                                            </IconButton>
                                            <IconButton size="small" color="error" onClick={() => handleDelete(config.id)}>
                                                <DeleteIcon fontSize="small" />
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
