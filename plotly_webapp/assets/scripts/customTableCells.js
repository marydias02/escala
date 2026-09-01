var dagcomponentfuncs = (window.dashAgGridComponentFunctions =
  window.dashAgGridComponentFunctions || {});
var dagfuncs = (window.dashAgGridFunctions = window.dashAgGridFunctions || {});

dagcomponentfuncs.HeaderWithIcon = function (props) {
  const { displayName, icon } = props;

  let iconElement;
  if (icon) {
    iconElement = React.createElement(window.dash_iconify.DashIconify, {
      icon: icon,
      style: { fontSize: "14px", marginRight: "4px" },
      key: "header-icon" + icon + displayName.trim(),
    });
  }

  return React.createElement(
    "div",
    {
      style: {
        display: "flex",
        alignItems: "center",
      },
    },
    [iconElement, displayName],
  );
};

dagcomponentfuncs.Priority = function (props) {
  const { value, setData } = props;

  let bg = "#eee",
    color = "#222";

  if (value === "High") {
    bg = "rgba(245, 234, 235, 1)"; // Negative colors
    color = "rgba(122, 31, 32, 1)";
    border = "rgba(239, 220, 220, 1)";
  } else if (value === "Medium") {
    bg = "rgba(241, 237, 218, 1)"; // Warning colors
    color = "rgba(74, 65, 28, 1)";
    border = "rgba(238, 232, 211, 1)";
  } else if (value === "Low") {
    bg = "rgba(234, 245, 237, 1)"; //Positive colors
    color = "rgba(28, 74, 40, 1)";
    border = "rgba(220, 239, 225, 1)";
  }

  function onClick() {
    if (setData) setData();
  }

  return React.createElement(
    "div",
    {
      onClick,
      style: {
        backgroundColor: bg,
        color: color,
        borderRadius: "4px",
        padding: "2px 6px",
        fontSize: ".8rem",
        marginTop: "7px",
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-start",
        boxSizing: "border-box",
        border: "1px solid transparent",
        borderColor: border,
        width: "fit-content",
        lineHeight: 1.5,
      },
    },
    [value],
  );
};

dagfuncs.priority_options = function () {
  return {
    values: ["High", "Medium", "Low"],
  };
};

dagcomponentfuncs.Action = function (props) {
  const { value, setData } = props;

  let bg = "#eee",
    color = "#222",
    icon = "lucide:arrow-right";

  if (value === "Validate Manually" || value === "Validação Manual") {
    bg = "rgba(245, 234, 235, 1)"; // Negative colors
    color = "rgba(122, 31, 32, 1)";
    border = "rgba(239, 220, 220, 1)";
    icon = "lucide:triangle-alert";
  } else if (value === "Sent back to Supplier") {
    bg = "rgba(241, 237, 218, 1)"; // Warning colors
    color = "rgba(74, 65, 28, 1)";
    border = "rgba(238, 232, 211, 1)";
    icon = "lucide:arrow-right";
  } else if (value === "Ingest in SAP" || value === "Ingerir em SAP") {
    bg = "rgba(234, 245, 237, 1)"; //Positive colors
    color = "rgba(28, 74, 40, 1)";
    border = "rgba(220, 239, 225, 1)";
    icon = "lucide:check";
  }

  function onClick() {
    if (setData) setData();
  }

  const iconElement = React.createElement(window.dash_iconify.DashIconify, {
    icon: icon,
    width: 14,
    height: 14,
    style: {
      marginRight: "2px",
    },
  });

  return React.createElement(
    "div",
    {
      onClick,
      style: {
        backgroundColor: bg,
        color: color,
        borderRadius: "4px",
        padding: "2px 6px",
        fontSize: ".8rem",
        marginTop: "7px",
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-start",
        boxSizing: "border-box",
        borderColor: "1px solid transparent",
        width: "fit-content",
        lineHeight: 1.5,
        fontWeight: 500,
      },
    },
    [iconElement, React.createElement("span", null, value)],
  );
};

dagfuncs.action_options = function () {
  return {
    values: [
      "Ingerir em SAP",
      "Retornado ao Fornecedor",
      "Encaminhar para Tesouraria",
      "Manter na Caixa de Entrada",
      "Validação Manual",
      "Ignorar (tem original)",
    ],
  };
};

dagcomponentfuncs.Status = function (props) {
  const { value, setData } = props;

  let bg = "#eee",
    color = "#222",
    icon = "lucide:arrow-right";

  if (value === "Erro") {
    bg = "rgba(245, 234, 235, 1)"; // Negative colors
    color = "rgba(122, 31, 32, 1)";
    border = "rgba(239, 220, 220, 1)";
    icon = "lucide:triangle-alert";
  } else if (value === "Comunicado" || value === "Sob Revisão") {
    bg = "rgba(241, 237, 218, 1)"; // Warning colors
    color = "rgba(74, 65, 28, 1)";
    border = "rgba(238, 232, 211, 1)";
    icon = "lucide:clock";
  } else if (value === "Ingerido") {
    bg = "rgba(234, 245, 237, 1)"; //Positive colors
    color = "rgba(28, 74, 40, 1)";
    border = "rgba(220, 239, 225, 1)";
    icon = "lucide:check";
  }

  function onClick() {
    if (setData) setData();
  }

  const iconElement = React.createElement(window.dash_iconify.DashIconify, {
    icon: icon,
    width: 14,
    height: 14,
    style: {
      marginRight: "2px",
    },
  });

  return React.createElement(
    "div",
    {
      onClick,
      style: {
        backgroundColor: bg,
        color: color,
        borderRadius: "4px",
        padding: "2px 6px",
        fontSize: ".8rem",
        marginTop: "7px",
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-start",
        boxSizing: "border-box",
        borderColor: "1px solid transparent",
        width: "fit-content",
        lineHeight: 1.5,
        fontWeight: 500,
      },
    },
    [iconElement, React.createElement("span", null, value)],
  );
};

dagfuncs.action_options = function () {
  return {
    values: [
      "Ingerir em SAP",
      "Retornado ao Fornecedor",
      "Encaminhar para Tesouraria",
      "Manter na Caixa de Entrada",
      "Validação Manual",
      "Ignorar (tem original)",
    ],
  };
};

dagcomponentfuncs.SAPStatus = function (props) {
  const { value, setData } = props;

  let bg = "#eee",
    color = "#222",
    icon = "lucide:arrow-right";

  if (
    value === "Necessita de validação manual" ||
    value === "Com resposta do buyer - a processar" ||
    value === "Novo processo não conforme"
  ) {
    bg = "rgba(245, 234, 235, 1)"; // Negative colors
    color = "rgba(122, 31, 32, 1)";
    border = "rgba(239, 220, 220, 1)";
    icon = "lucide:triangle-alert";
  } else if (value === "Em resolução pelo buyer") {
    bg = "rgba(241, 237, 218, 1)"; // Warning colors
    color = "rgba(74, 65, 28, 1)";
    border = "rgba(238, 232, 211, 1)";
    icon = "lucide:clock";
  } else if (
    value === "Processamento automático" ||
    value === "Processado pelo agente" ||
    value === "Processado manualmente"
  ) {
    bg = "rgba(234, 245, 237, 1)"; //Positive colors
    color = "rgba(28, 74, 40, 1)";
    border = "rgba(220, 239, 225, 1)";
    icon = "lucide:check";
  }

  function onClick() {
    if (setData) setData();
  }

  const iconElement = React.createElement(window.dash_iconify.DashIconify, {
    icon: icon,
    width: 14,
    height: 14,
    style: {
      marginRight: "2px",
    },
  });

  return React.createElement(
    "div",
    {
      onClick,
      style: {
        backgroundColor: bg,
        color: color,
        borderRadius: "4px",
        padding: "2px 6px",
        fontSize: ".8rem",
        marginTop: "7px",
        display: "flex",
        alignItems: "center",
        justifyContent: "flex-start",
        boxSizing: "border-box",
        borderColor: "1px solid transparent",
        width: "fit-content",
        lineHeight: 1.5,
        fontWeight: 500,
      },
    },
    [iconElement, React.createElement("span", null, value)],
  );
};
