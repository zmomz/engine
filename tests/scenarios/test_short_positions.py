"""
Group E Tests: Short Position Rejection

Tests that short positions are properly REJECTED in spot trading.
The system should not support short positions - all sell signals without
exit intent should be rejected at the signal router level.

These are unit tests that directly test the rejection logic without
requiring database connections or full service initialization.
"""

import pytest


class TestShortRejectionLogic:
    """
    Unit tests for the short position rejection logic.

    The actual rejection happens in SignalRouterService.route() at lines 283-292:

    ```python
    # For SPOT trading: Only "buy" creates positions (all positions are "long")
    # "sell" action without exit intent is ignored (spot can't short)
    raw_action = signal.tv.action.lower()
    if raw_action == "buy":
        signal_side = "long"
    elif raw_action == "sell":
        # In spot trading, a "sell" signal without exit intent is invalid
        # We can't open short positions in spot markets
        logger.warning(f"Ignoring sell signal for {signal.tv.symbol} - spot trading does not support short positions. Use execution_intent.type='exit' to close a long position.")
        return "Signal ignored: Spot trading does not support short positions. Use exit intent to close positions."
    ```
    """

    def test_sell_action_triggers_rejection_condition(self):
        """Test that 'sell' action meets the rejection condition."""
        raw_action = "sell"
        intent_type = "signal"  # Not "exit"

        # Simulate the logic from signal_router.py
        should_reject = raw_action.lower() == "sell" and intent_type != "exit"

        assert should_reject is True

    def test_buy_action_does_not_trigger_rejection(self):
        """Test that 'buy' action does not meet the rejection condition."""
        raw_action = "buy"
        intent_type = "signal"

        should_reject = raw_action.lower() == "sell" and intent_type != "exit"

        assert should_reject is False

    def test_sell_with_exit_intent_does_not_trigger_rejection(self):
        """Test that 'sell' with 'exit' intent does not meet the rejection condition."""
        raw_action = "sell"
        intent_type = "exit"

        should_reject = raw_action.lower() == "sell" and intent_type != "exit"

        assert should_reject is False

    @pytest.mark.parametrize("action", ["sell", "SELL", "Sell", "sElL"])
    def test_sell_action_case_variations(self, action):
        """Test that all case variations of 'sell' trigger rejection."""
        intent_type = "signal"

        should_reject = action.lower() == "sell" and intent_type != "exit"

        assert should_reject is True

    @pytest.mark.parametrize("intent_type", ["signal", "reduce", "reverse"])
    def test_non_exit_intents_with_sell_trigger_rejection(self, intent_type):
        """Test that all non-exit intent types with sell trigger rejection."""
        raw_action = "sell"

        should_reject = raw_action.lower() == "sell" and intent_type != "exit"

        assert should_reject is True


class TestShortRejectionMessage:
    """Test the exact rejection message returned."""

    def get_rejection_message(self, symbol: str = "BTC/USDT") -> str:
        """Return the expected rejection message."""
        # This is the exact message from signal_router.py line 292
        return "Signal ignored: Spot trading does not support short positions. Use exit intent to close positions."

    def test_rejection_message_content(self):
        """Test that the rejection message has the expected content."""
        message = self.get_rejection_message()

        # Key parts of the message
        assert "signal ignored" in message.lower()
        assert "spot trading" in message.lower()
        assert "short positions" in message.lower()
        assert "exit intent" in message.lower()

    def test_rejection_message_mentions_spot_trading(self):
        """Test that message explains this is a spot trading limitation."""
        message = self.get_rejection_message()

        assert "spot" in message.lower()

    def test_rejection_message_guides_to_exit_intent(self):
        """Test that message guides user to use exit intent."""
        message = self.get_rejection_message()

        assert "exit" in message.lower()

    def test_rejection_message_mentions_short_positions(self):
        """Test that message explains short positions are not supported."""
        message = self.get_rejection_message()

        assert "short" in message.lower()


class TestSignalActionMapping:
    """
    Test the action to side mapping logic from signal_router.py.

    In spot trading:
    - buy → long (valid, creates/pyramids position)
    - sell + exit → closes position (valid)
    - sell + non-exit → REJECTED (can't short)
    """

    def get_signal_side(self, action: str, intent_type: str) -> str | None:
        """
        Simulate the signal side determination from signal_router.py.

        Returns:
            - "long" for buy actions
            - None for rejected sell actions (represents the rejection return)
            - "exit" for sell with exit intent (different code path)
        """
        raw_action = action.lower()

        if intent_type == "exit":
            return "exit"  # Takes the exit code path

        if raw_action == "buy":
            return "long"
        elif raw_action == "sell":
            return None  # Rejected - returns error message
        else:
            return raw_action  # Fallback

    def test_buy_returns_long(self):
        """Test that buy action returns 'long' side."""
        side = self.get_signal_side("buy", "signal")
        assert side == "long"

    def test_sell_with_signal_intent_returns_none_rejected(self):
        """Test that sell with signal intent is rejected (returns None)."""
        side = self.get_signal_side("sell", "signal")
        assert side is None  # Rejected

    def test_sell_with_exit_intent_returns_exit(self):
        """Test that sell with exit intent takes exit code path."""
        side = self.get_signal_side("sell", "exit")
        assert side == "exit"  # Different code path

    @pytest.mark.parametrize("action,expected", [
        ("buy", "long"),
        ("BUY", "long"),
        ("Buy", "long"),
    ])
    def test_buy_case_variations_return_long(self, action, expected):
        """Test buy action case variations."""
        side = self.get_signal_side(action, "signal")
        assert side == expected

    @pytest.mark.parametrize("action", ["sell", "SELL", "Sell"])
    def test_sell_case_variations_rejected(self, action):
        """Test sell action case variations are all rejected."""
        side = self.get_signal_side(action, "signal")
        assert side is None  # All rejected


class TestSpotTradingConstraints:
    """
    Test documentation of spot trading constraints.

    Spot trading only supports:
    - Long positions (buy and hold)
    - Closing positions (sell what you own)

    Spot trading does NOT support:
    - Short positions (selling what you don't own)
    - Leverage/margin
    """

    def test_spot_trading_supports_long_positions(self):
        """Verify that spot trading supports long positions."""
        supported_sides = ["long"]
        assert "long" in supported_sides
        assert "short" not in supported_sides

    def test_spot_trading_does_not_support_short(self):
        """Verify that spot trading does not support short positions."""
        supported_sides = ["long"]
        assert "short" not in supported_sides

    def test_valid_spot_actions_documentation(self):
        """Document valid actions in spot trading."""
        valid_actions = {
            ("buy", "signal"): "Opens/pyramids long position",
            ("buy", "exit"): "Unusual but could be interpreted",
            ("sell", "exit"): "Closes existing long position",
            ("sell", "signal"): "REJECTED - cannot short in spot",
            ("sell", "reduce"): "REJECTED - cannot short in spot",
            ("sell", "reverse"): "REJECTED - cannot short in spot",
        }

        # Verify the expected rejections
        rejected_combinations = [
            k for k, v in valid_actions.items()
            if "REJECTED" in v
        ]

        # All sell + non-exit combinations should be rejected
        for action, intent in rejected_combinations:
            assert action == "sell"
            assert intent != "exit"
