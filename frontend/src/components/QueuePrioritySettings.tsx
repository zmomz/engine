import React from 'react';
import { Controller } from 'react-hook-form';
import {
    Box,
    Typography,
    Switch,
    Paper,
    List,
    ListItem,
    ListItemText,
    Chip,
    Alert
} from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    TouchSensor,
    useSensor,
    useSensors,
    DragEndEvent,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
    useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const RULE_LABELS = {
    same_pair_timeframe: {
        label: 'Same Pair & Timeframe',
        description: 'Pyramid continuation of an already active position (bypasses max position limit)'
    },
    deepest_loss_percent: {
        label: 'Deepest Current Loss',
        description: 'Deeper loss means better discount zone for averaging in'
    },
    highest_replacement: {
        label: 'Highest Replacement Count',
        description: 'Signal replaced multiple times indicates repeated strategy confirmation'
    },
    fifo_fallback: {
        label: 'FIFO (First In First Out)',
        description: 'Oldest queued signal as fair tiebreak rule'
    }
};

interface SortableItemProps {
    id: string;
    index: number;
    ruleName: string;
    isEnabled: boolean;
    onToggle: (checked: boolean) => void;
    enabledCount: number;
}

function SortableItem({ id, index, ruleName, isEnabled, onToggle, enabledCount }: SortableItemProps) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    const ruleInfo = RULE_LABELS[ruleName as keyof typeof RULE_LABELS];
    if (!ruleInfo) return null;

    return (
        <ListItem
            ref={setNodeRef}
            style={style}
            sx={{
                mb: 1,
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                cursor: 'grab',
                flexWrap: { xs: 'wrap', sm: 'nowrap' },
                gap: { xs: 1, sm: 0 },
                pr: { xs: 1, sm: 2 },
                '&:hover': {
                    bgcolor: 'action.hover'
                }
            }}
        >
            <div {...attributes} {...listeners} style={{ marginRight: 8, cursor: 'grab', flexShrink: 0, touchAction: 'none' }}>
                <DragIndicatorIcon color="action" />
            </div>

            <Chip
                label={index + 1}
                size="small"
                color="primary"
                sx={{ mr: { xs: 1, sm: 2 }, flexShrink: 0 }}
            />

            <ListItemText
                primary={ruleInfo.label}
                secondary={ruleInfo.description}
                sx={{
                    minWidth: 0,
                    flexBasis: { xs: '100%', sm: 'auto' },
                    order: { xs: 2, sm: 0 },
                    ml: { xs: 4, sm: 0 }
                }}
                primaryTypographyProps={{
                    sx: { fontSize: { xs: '0.875rem', sm: '1rem' } }
                }}
                secondaryTypographyProps={{
                    sx: {
                        fontSize: { xs: '0.7rem', sm: '0.75rem' },
                        display: { xs: 'none', sm: 'block' }
                    }
                }}
            />

            <Box sx={{ ml: 'auto', flexShrink: 0 }}>
                <Switch
                    checked={isEnabled}
                    onChange={(e) => onToggle(e.target.checked)}
                    disabled={isEnabled && enabledCount === 1}
                    size="small"
                />
            </Box>
        </ListItem>
    );
}

interface QueuePrioritySettingsProps {
    control: any;
    setValue: any;
    watch: any;
}

const QueuePrioritySettings: React.FC<QueuePrioritySettingsProps> = ({ control, setValue, watch }) => {

    const priorityRulesEnabled = watch('riskEngineConfig.priority_rules.priority_rules_enabled');
    const priorityOrder = watch('riskEngineConfig.priority_rules.priority_order') || ["same_pair_timeframe",
        "deepest_loss_percent",
        "highest_replacement",
        "fifo_fallback"];

    // Check if at least one rule is enabled
    const enabledCount = priorityRulesEnabled
        ? Object.values(priorityRulesEnabled).filter(Boolean).length
        : 0;

    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 8, // 8px movement required before drag starts
            },
        }),
        useSensor(TouchSensor, {
            activationConstraint: {
                delay: 150, // 150ms hold before drag starts
                tolerance: 5, // 5px movement tolerance during delay
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;

        if (over && active.id !== over.id) {
            const oldIndex = priorityOrder.indexOf(active.id);
            const newIndex = priorityOrder.indexOf(over.id);

            const newOrder = arrayMove(priorityOrder, oldIndex, newIndex);
            setValue('riskEngineConfig.priority_rules.priority_order', newOrder, { shouldDirty: true });
        }
    };

    return (
        <Box sx={{ mt: { xs: 1, sm: 3 } }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: { xs: '0.95rem', sm: '1.1rem' }, mb: 0.5 }}>
                Queue Priority Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontSize: { xs: '0.75rem', sm: '0.875rem' } }}>
                Configure priority rules and drag to reorder.
            </Typography>

            {enabledCount === 0 && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                    At least one priority rule must be enabled
                </Alert>
            )}

            <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                >
                    <SortableContext
                        items={priorityOrder}
                        strategy={verticalListSortingStrategy}
                    >
                        <List dense>
                            {priorityOrder.map((ruleName: string, index: number) => (
                                <Controller
                                    key={ruleName}
                                    name={`riskEngineConfig.priority_rules.priority_rules_enabled.${ruleName}`}
                                    control={control}
                                    render={({ field }) => (
                                        <SortableItem
                                            id={ruleName}
                                            index={index}
                                            ruleName={ruleName}
                                            isEnabled={field.value}
                                            onToggle={field.onChange}
                                            enabledCount={enabledCount}
                                        />
                                    )}
                                />
                            ))}
                        </List>
                    </SortableContext>
                </DndContext>

                <Box sx={{ mt: 2, p: 1, bgcolor: 'info.50', borderRadius: 1, display: { xs: 'none', sm: 'block' } }}>
                    <Typography variant="caption" color="text.secondary">
                        <strong>ℹ How it works:</strong> Signals are evaluated against rules in order from top to bottom.
                        The first matching enabled rule determines the signal's priority.
                    </Typography>
                </Box>
            </Paper>
        </Box>
    );
};

export default QueuePrioritySettings;
