# Select

The Select component wraps `dcc.Dropdown` with project styling and convenience options (labels, messages, error state).

## Basic Usage

```python
from components.select.select import Select

Select(
    select_options=["New York City", "Montreal", "San Francisco"],
    placeholder="Choose a city",
    value="Montreal",
    label="City",
    additional_message="You can search in the list",
)
```

## Properties

- **select_options**: Required. Accepts:
  - `dict` of `{label: value}` (disabled option defaults to `False`)
  - `list[str]` (labels are the same as values and are derived from the list items)
  - `list[dict]` with `{"label":"", "value":"", "disabled":False},{"label":"", "value":"", "disabled":True} `
- **value**: Optional default selection. Can be a string, dict, or list (for `multi=True`).
- **placeholder**: Placeholder text when no value is selected.
- **multi**: Enable multi-select (default `False`).
- **clearable**: Show clear icon (default `True`).
- **closeOnSelect**: Close menu after selection (default `True`).
- **disabled**: Disable the control (default `False`).
- **searchable**: Enable search (default `True`).
- **id_select**: Optional ID for the underlying dropdown (used to wire labels/messages).
- **wrapper_className**: Additional class on the wrapper `div`.
- **label**: Optional label text above the select.
- **additional_message**: Optional helper text below the select.
- **has_error**: Toggle error styling (default `False`).
- **error_message**: Error text displayed when `has_error=True`.

## Color Modes

The component supports two color modes via the wrapper class:

- **default** (default): default color that should be used in light backgrounds
- **custom_light**: this color mode uses light font colors and should be used with dark background colors

When reusing `custom_light`, you must provide `select_background_color` with a CSS variable taht should match your dark background color:

```python
Select(
    select_options=["NYC", "MTL", "SF"],
    select_color_mode="custom_light",
    select_background_color="var(--accent-sidebar)",
)
```

## Width

Default width is set in CSS:

- `.select { width: 200px; }`
- `.select .Select--multi { width: 300px; }`

when using this component this width should be changed so that the select component takes a percentage of the parent component. However if there is no parent component and no value pre selected without a fixed width the seelct will have no width

To change the width, you can change it direclty in the css classes mentioned above or override the wrapper or add a custom class:

```python
Select(
    select_options=["NYC", "MTL", "SF"],
    wrapper_className="select--wide",
)
```

```css
.select.select--wide {
  width: 320px;
}
```
