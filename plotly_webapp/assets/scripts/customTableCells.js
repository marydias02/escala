var dagcomponentfuncs = (window.dashAgGridComponentFunctions =
    window.dashAgGridComponentFunctions || {})
var dagfuncs = (window.dashAgGridFunctions = window.dashAgGridFunctions || {})

dagcomponentfuncs.HeaderWithIcon = function (props) {
    const { displayName, icon } = props

    let iconElement
    if (icon) {
        iconElement = React.createElement(window.dash_iconify.DashIconify, {
            icon: icon,
            style: { fontSize: '14px', marginRight: '4px' },
            key: 'header-icon' + icon + displayName.trim(),
        })
    }

    return React.createElement(
        'div',
        {
            style: {
                display: 'flex',
                alignItems: 'center',
            },
        },
        [iconElement, displayName]
    )
}

dagcomponentfuncs.Priority = function (props) {
    const { value, setData } = props

    let bg = '#eee',
        color = '#222'

    if (value === 'High') {
        bg = 'rgba(245, 234, 235, 1)' // Negative colors
        color = 'rgba(122, 31, 32, 1)'
        border = 'rgba(239, 220, 220, 1)'
    } else if (value === 'Medium') {
        bg = 'rgba(241, 237, 218, 1)' // Warning colors
        color = 'rgba(74, 65, 28, 1)'
        border = 'rgba(238, 232, 211, 1)'
    } else if (value === 'Low') {
        bg = 'rgba(234, 245, 237, 1)' //Positive colors
        color = 'rgba(28, 74, 40, 1)'
        border = 'rgba(220, 239, 225, 1)'
    }

    function onClick() {
        if (setData) setData()
    }

    return React.createElement(
        'div',
        {
            onClick,
            style: {
                backgroundColor: bg,
                color: color,
                borderRadius: '4px',
                padding: '2px 6px',
                fontSize: '.8rem',
                marginTop: '7px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                boxSizing: 'border-box',
                border: '1px solid transparent',
                borderColor: border,
                width: 'fit-content',
                lineHeight: 1.5,
            },
        },
        [value]
    )
}

dagfuncs.priority_options = function () {
    return {
        values: ['High', 'Medium', 'Low'],
    }
}
