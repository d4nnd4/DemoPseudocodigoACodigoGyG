"""
Este es el catálogo de lenguajes destino y prompts específicos para cada uno.
"""

from dataclasses import dataclass

TO_CODE = "to_code"      # pseudocódigo -> código
TO_PSEUDO = "to_pseudo"  # código -> pseudocódigo
DIRECTIONS = (TO_CODE, TO_PSEUDO)


@dataclass(frozen=True)
class Language:
    id: str
    label: str
    extension: str
    # id de lenguaje para el editor Monaco
    monaco: str  
    guidelines: str
    example: str = ""
    # Si el lenguaje exige un nombre de archivo concreto (Java: clase pública Main -> Main.java),
    fixed_filename: str | None = None
    # Pistas para la conversión de código a pseudo
    reverse_hints: str = ""
    # Aviso que el frontend muestra al elegir el lenguaje
    note: str = ""


BASE_SYSTEM_PROMPT = """You are a senior software engineer that translates pseudocode into \
production-quality source code.

Rules:
- Output ONLY the source code. No explanations before or after it.
- Do NOT wrap the answer in markdown fences.
- Implement exactly the logic described by the pseudocode, keeping the same order of steps.
- Use clear names derived from the pseudocode. Short comments are allowed where they help.
- If the pseudocode reads input or prints output, do the same using the idiomatic
  standard-library mechanism of the target language.
- The program must compile / run as-is.

Target language: {label}
{guidelines}
"""

LANGUAGES: dict[str, Language] = {
    "python": Language(
        id="python",
        label="Python 3.12",
        extension="py",
        monaco="python",
        guidelines="""- Use type hints and functions.
- Put the entry point under `if __name__ == "__main__":`.
- Only use the standard library.""",
    ),
    "go": Language(
        id="go",
        label="Go 1.22",
        extension="go",
        monaco="go",
        guidelines="""- Produce a single file with `package main` and a `func main()`.
- Only use the standard library; include every import you use and no unused imports.
- Handle errors explicitly.""",
    ),
    "typescript": Language(
        id="typescript",
        label="TypeScript 5 (Node.js)",
        extension="ts",
        monaco="typescript",
        guidelines="""- Strict typing: no `any`.
- Target Node.js; for console input use `node:readline/promises`.
- Wrap the entry point in an async `main()` function and call it.""",
    ),
    "java": Language(
        id="java",
        label="Java 21",
        extension="java",
        monaco="java",
        fixed_filename="Main.java",
        guidelines="""- Produce a single file whose only public class is `public class Main`
  with `public static void main(String[] args)`.
- Only use the JDK standard library; include all imports.
- For console input use `java.util.Scanner` (close it at the end).
- Extract helper logic into private static methods.""",
    ),
    "csharp": Language(
        id="csharp",
        label="C# 12 (.NET 8)",
        extension="cs",
        monaco="csharp",
        guidelines="""- Console application with a `Program` class and `static void Main()`
  (do NOT use top-level statements).
- Only use the .NET base class library (`System`, `System.Linq`, `System.Collections.Generic`).
- Use `Console.ReadLine()` / `Console.WriteLine()` and `int.Parse` / `TryParse` for input.
- Follow .NET naming conventions (PascalCase methods, camelCase locals).""",
    ),
    "vbnet": Language(
        id="vbnet",
        label="Visual Basic .NET (.NET 8)",
        extension="vb",
        monaco="vb",
        guidelines="""- Start with `Option Strict On` and `Option Explicit On`.
- Console application: `Module Program` with `Sub Main()`.
- Declare every variable with `Dim ... As <Type>`.
- Use `Console.ReadLine()` / `Console.WriteLine()`; convert input with `Integer.Parse` / `CInt`.
- Use VB.NET syntax only (`If ... Then ... End If`, `For ... Next`, `While ... End While`).""",
    ),
    "asp": Language(
        id="asp",
        label="ASP Classic (VBScript)",
        extension="asp",
        monaco="vb",
        guidelines="""- Classic ASP page (IIS) using VBScript — NOT ASP.NET.
- First line: `<%@ Language="VBScript" %>`, then `<% Option Explicit %>`.
- Declare variables with `Dim` (VBScript has no types; use CInt/CDbl/CStr to convert).
- Input that the pseudocode READS comes from `Request.Form` (POST); render a minimal
  HTML <form method="post"> to send it when needed.
- Output with `Response.Write`, escaping text with `Server.HTMLEncode`.
- Wrap the result in a minimal valid HTML page.""",
        reverse_hints="""- Request.Form / Request.QueryString values are inputs (LEER).
- Response.Write is output (IMPRIMIR). Ignore HTML markup that is only layout.""",
    ),
    "rpgle": Language(
        id="rpgle",
        label="IBM i (AS400) · RPGLE",
        extension="rpgle",
        monaco="rpgle",
        note=("IBM i / AS400: de momento solo está disponible RPGLE free-format (**FREE). "
              "CL, COBOL/400 y DDS aún no. Revisa el código antes de compilarlo."),
        reverse_hints="""- DSPLY shows a message (IMPRIMIR) or, with a response variable, reads input (LEER).
- `*inlr = *on; return;` is just the end of the program (FIN).
- DCL-S declares a variable: mention it only when it gets its initial value.
- If the source is fixed-format (C-specs), interpret it anyway.""",
        guidelines="""- Use fully free-format RPG (**FREE on the first line).
- Declare everything with DCL-S, DCL-DS, DCL-PR, DCL-PI, DCL-PROC.
- Use `ctl-opt dftactgrp(*no) actgrp(*caller);`.
- Use DSPLY for simple console output/input (messages up to 52 chars).
- Use %char, %dec, %int, %trim, %len, etc. built-in functions.
- End the main program with `*inlr = *on;` and `return;`.
- Never use fixed-format columns (no C-specs, D-specs or F-specs in fixed form).""",
        example="""Example of the expected style:
**FREE
ctl-opt dftactgrp(*no) actgrp(*caller);

dcl-s total packed(9:2) inz(0);
dcl-s i int(10);
dcl-s msg char(52);

for i = 1 to 10;
  total += i;
endfor;

msg = 'Total: ' + %char(total);
dsply msg;

*inlr = *on;
return;""",
    ),
}



#  Dirección inversa: código -> pseudocódigo (en español, mismo estilo que la entrada)
PSEUDO_SYSTEM_PROMPT = """You are a programming teacher that explains source code as clear, \
structured PSEUDOCODE written in SPANISH.

Rules:
- Output ONLY the pseudocode. No explanations before or after it. No markdown fences.
- Write it in Spanish, using exactly these keywords (UPPERCASE):
  INICIO / FIN, LEER x, IMPRIMIR "texto", x
  x <- valor                          (assignment)
  SI cond ENTONCES ... SINO ... FIN SI
  SEGUN x HACER  CASO v: ...  DE OTRO MODO: ...  FIN SEGUN
  MIENTRAS cond HACER ... FIN MIENTRAS
  REPETIR ... HASTA QUE cond
  PARA i DESDE a HASTA b [CON PASO p] HACER ... FIN PARA
  PARA CADA x EN lista HACER ... FIN PARA
  FUNCION nombre(param1, param2) ... RETORNAR valor ... FIN FUNCION
  Y, O, NO, MOD, =, <>, <, >, <=, >=
- Indent nested blocks with two spaces.
- Keep the same order of steps as the code. Describe WHAT is done, not language syntax:
  omit imports, type declarations, class boilerplate, `main` wrappers and error-handling
  plumbing unless they change the logic.
- Keep the original variable and function names (translate them only if they are trivial).
- Library calls become a short description, e.g. `lista <- ORDENAR(lista)`.

Example:
INICIO
  LEER n
  suma <- 0
  PARA i DESDE 1 HASTA n HACER
    SI i MOD 2 = 0 ENTONCES
      suma <- suma + i
    FIN SI
  FIN PARA
  IMPRIMIR "La suma de los pares es: ", suma
FIN

Source language: {label}
{hints}
"""


def build_system_prompt(lang: Language, direction: str = TO_CODE) -> str:
    if direction == TO_PSEUDO:
        return PSEUDO_SYSTEM_PROMPT.format(label=lang.label, hints=lang.reverse_hints)
    prompt = BASE_SYSTEM_PROMPT.format(label=lang.label, guidelines=lang.guidelines)
    if lang.example:
        prompt += "\n" + lang.example + "\n"
    return prompt


def build_user_prompt(source: str, lang: Language, direction: str = TO_CODE) -> str:
    if direction == TO_PSEUDO:
        return (
            f"Explain the following {lang.label} code as Spanish pseudocode.\n\n"
            f"CODE:\n{source.strip()}\n\n"
            "PSEUDOCÓDIGO:"
        )
    return (
        f"Translate the following pseudocode into {lang.label}.\n\n"
        f"PSEUDOCODE:\n{source.strip()}\n\n"
        f"{lang.label} CODE:"
    )
