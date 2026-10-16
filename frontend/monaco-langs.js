// Lenguajes y temas extra para Monaco: RPGLE free-format y el pseudocódigo en español.
window.registerExtraLanguages = function (monaco) {
  registerRpgle(monaco);
  registerPseudo(monaco);
  registerThemes(monaco);
};

// Resaltado de sintaxis básico para RPGLE free-format (Monaco no lo trae de fábrica).
function registerRpgle(monaco) {
  monaco.languages.register({ id: "rpgle", extensions: [".rpgle", ".sqlrpgle"] });
  monaco.languages.setMonarchTokensProvider("rpgle", {
    ignoreCase: true,
    keywords: [
      "ctl-opt", "dcl-s", "dcl-c", "dcl-ds", "end-ds", "dcl-pr", "end-pr", "dcl-pi", "end-pi",
      "dcl-proc", "end-proc", "dcl-f", "dcl-subf", "dcl-parm", "if", "elseif", "else", "endif",
      "dow", "dou", "enddo", "for", "to", "downto", "by", "endfor", "select", "when", "other",
      "endsl", "monitor", "on-error", "endmon", "return", "leave", "iter", "exsr", "begsr",
      "endsr", "callp", "eval", "dsply", "read", "reade", "chain", "write", "update", "delete",
      "setll", "setgt", "open", "close", "exec", "sql", "and", "or", "not", "inz", "const",
      "value", "options", "export", "extproc", "likeds", "like", "dim", "qualified", "template",
    ],
    types: ["char", "varchar", "packed", "zoned", "int", "uns", "ind", "date", "time", "timestamp", "pointer", "float", "bindec", "graph", "ucs2"],
    tokenizer: {
      root: [
        [/\*\*free/, "keyword.directive"],
        [/\/\/.*$/, "comment"],
        [/'([^']|'')*'/, "string"],
        [/%[a-z]+/, "predefined"],
        [/\*[a-z]+/, "constant"],
        [/\d+(\.\d+)?/, "number"],
        [/[a-z_][\w-]*/, { cases: { "@keywords": "keyword", "@types": "type", "@default": "identifier" } }],
        [/[;:(),=+\-*/<>]/, "delimiter"],
      ],
    },
  });
  monaco.languages.setLanguageConfiguration("rpgle", {
    comments: { lineComment: "//" },
    brackets: [["(", ")"]],
    autoClosingPairs: [{ open: "(", close: ")" }, { open: "'", close: "'" }],
  });
}

// Pseudocódigo con las palabras clave que usa la app (entrada y salida).
function registerPseudo(monaco) {
  monaco.languages.register({ id: "pseudo" });
  monaco.languages.setMonarchTokensProvider("pseudo", {
    ignoreCase: false,
    keywords: [
      "INICIO", "FIN", "ALGORITMO", "PROCESO", "LEER", "ESCRIBIR", "IMPRIMIR", "MOSTRAR", "SI", "ENTONCES",
      "SINO", "SEGUN", "CASO", "DE", "OTRO", "MODO", "MIENTRAS", "HACER", "REPETIR", "HASTA", "QUE",
      "PARA", "CADA", "EN", "DESDE", "CON", "PASO", "FUNCION", "PROCEDIMIENTO", "RETORNAR", "DEVOLVER",
      "TERMINAR", "ROMPER", "CONTINUAR", "DEFINIR", "COMO", "ENTERO", "REAL", "CADENA", "LOGICO", "ARREGLO",
      "LISTA", "MAPA", "PILA", "COLA", "NULO", "VERDADERO", "FALSO",
    ],
    operators: ["Y", "O", "NO", "MOD", "DIV"],
    tokenizer: {
      root: [
        [/\/\/.*$/, "comment"],
        [/"([^"\\]|\\.)*"/, "string"],
        [/'([^'\\]|\\.)*'/, "string"],
        [/<-|←|<=|>=|<>|!=|==|[=<>+\-*/^]/, "operator"],
        [/\d+(\.\d+)?/, "number"],
        [/[A-ZÁÉÍÓÚÑ_]+(?![a-záéíóúñ0-9_])/, { cases: { "@keywords": "keyword", "@operators": "keyword.operator", "@default": "identifier" } }],
        [/[a-zA-Z_áéíóúñÁÉÍÓÚÑ][\wáéíóúñÁÉÍÓÚÑ]*/, "identifier"],
      ],
    },
  });
  monaco.languages.setLanguageConfiguration("pseudo", {
    comments: { lineComment: "//" },
    brackets: [["(", ")"], ["[", "]"]],
    autoClosingPairs: [{ open: "(", close: ")" }, { open: "[", close: "]" }, { open: '"', close: '"' }],
  });
}

// Temas a juego con el logo: azul marino + teal + plata.
function registerThemes(monaco) {
  monaco.editor.defineTheme("gyg-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "4FB3D1", fontStyle: "bold" },
      { token: "keyword.operator", foreground: "8FB8E8" },
      { token: "string", foreground: "B5D99C" },
      { token: "comment", foreground: "6B7AA8", fontStyle: "italic" },
      { token: "number", foreground: "F2C078" },
    ],
    colors: {
      "editor.background": "#0E1638",
      "editor.lineHighlightBackground": "#16205A",
      "editorLineNumber.foreground": "#4A5788",
      "editorLineNumber.activeForeground": "#B9C4E4",
      "editor.selectionBackground": "#2186A455",
      "editorCursor.foreground": "#4FB3D1",
      "editorIndentGuide.background1": "#1E2A66",
    },
  });
  monaco.editor.defineTheme("gyg-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "283A83", fontStyle: "bold" },
      { token: "keyword.operator", foreground: "2186A4" },
      { token: "string", foreground: "3D7A2A" },
      { token: "comment", foreground: "7A86A8", fontStyle: "italic" },
      { token: "number", foreground: "A15C00" },
    ],
    colors: {
      "editor.background": "#FBFCFE",
      "editor.lineHighlightBackground": "#EEF2F8",
      "editorLineNumber.foreground": "#A3ADC8",
      "editorLineNumber.activeForeground": "#283A83",
      "editor.selectionBackground": "#2186A433",
      "editorCursor.foreground": "#2186A4",
    },
  });
}
