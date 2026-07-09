# Indicator Card

The Indicator Card component displays one or more metric rows, each with a value, optional caption, and optional delta badge. It can also show an optional label with a tooltip icon.

## Basic Usage

```python
from components.cards.indicator_card.indicator_card import IndicatorCard

IndicatorCard(
    label_text="Performance",
    label_tooltip="Compared to last period",
    rows=[
        ("98.2%", "New Users", "+1.4%", "increase")
    ],
)
```

## Properties

- **label_text**: Optional label shown at the top of the card
- **label_tooltip**: Optional tooltip text; shown on hover on an info icon next to the label
- **rows**: List of tuples that define the card rows. For each row the value is required, the other elements can be 'None'

## Rows Structure

Each row is a tuple with the following fields:

1. **value**: The main value shown in large text (string or number)
2. **caption**: Optional description text shown below the value
3. **badge_value**: Optional badge text (e.g. "+1.4%")
4. **badge_delta**: Optional delta type for the badge: "increase" or "decrease"

If either **badge_value** or **badge_delta** is `None`, the badge is not displayed.
