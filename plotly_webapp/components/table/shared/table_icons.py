SORT_ASCENDING_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" '
    'viewBox="0 0 24 24"><path fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
    'd="m5 12l7-7l7 7m-7 7V5"/></svg>'
)
SORT_DESCENDING_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" '
    'viewBox="0 0 24 24"><path fill="none" stroke="currentColor" '
    'stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
    'd="M12 5v14m7-7l-7 7l-7-7"/></svg>'
)
FILTER_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20a1 1 0 0 0 .553.895l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .517-1.341L21.74 4.67A1 1 0 0 0 21 3H3a1 1 0 0 0-.742 1.67l7.225 7.989A2 2 0 0 1 10 14z"/></svg>'

default_icon_options = {
    "icons": {
        "sortAscending": SORT_ASCENDING_SVG,
        "sortDescending": SORT_DESCENDING_SVG,
        "filter": FILTER_SVG,
    },
}
