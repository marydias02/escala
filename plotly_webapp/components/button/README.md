# Buttons

Button has all the default html.Button props, exactly as you're used to using them!
However, we get a few extra options here. 

Note that, they are all completely optional!

## Size

You can add a size for your button. We have the following sizes available:
- xs
- sm
- md

The default size is **md**.

## Icon

We get a prop ready to receive the string of your desired **Lucide Icon**. It's powered by Dash-Iconify.

```python
Button(icon="lucide:star", id="star-button"),
```

Just add the string identifier you can find here: https://icon-sets.iconify.design/lucide/

## Variants

You can adjust your buttons between the following options:
- Primary: Has a background, the color of your accent color.
- Outline: Has a subtle outline
- Ghost: Doesn't have a background.

The default variant is **Primary**.

Note: If you have multiple buttons on the same component, please consider only leaving the main action with the Primary variant.

## Destructive

You can toggle this with true or false. By default, it's **False**. 
This is reserved for actions like Delete, Cancel, and so on.

```python
Button("Delete", icon="lucide:trash-2", variant="outline", destructive=True, id="delete-button"),
```

## Loading

If you're executing a callback that may take a while, consider adding the Loading style like this.

```python
Button("Approve", loading=True, id="approve-button"),
```