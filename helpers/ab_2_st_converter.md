### Intended use

This script is intended to convert Automation Basic code to Structured Text code. It can be used as a starting point for porting existing Automation Basic code to Structured Text. However, the generated Structured Text code may require manual adjustments and testing to ensure it works correctly in the target environment.

### What will be converted

- Comments of type (* ... *) are converted to // comments in Structured Text.
- Semicolons are added at the end of each statement in Structured Text.
- Keywords are converted from Automation Basic syntax to Structured Text syntax. For example, `if ... then ... else ... endif` is converted to `IF ... THEN ... ELSE ... END_IF`.
- Lowercase keywords are converted to uppercase keywords in Structured Text.
- Hex and binary literals are converted to Structured Text format. For example, `$FF` is converted to `16#FF` and `%1010` is converted to `2#1010`.
- Convert select statements from Automation Basic to case statements in Structured Text. The select states must be defined with constant values, otherwise the compiler will raise an error for non-constant case values.
- Convert loop statements from Automation Basic to for statements in Structured Text.
- Convert case statements from Automation Basic to for statements in Structured Text.
- Math functions INC and DEC are converted to `+ 1` and `- 1` respectively.
- Assignment operator `=` is converted to `:=` in Structured Text.
- EXITIF statements are converted to IF ... THEN ... END_IF statements with a RETURN statement inside.
- Function block calls are converted to Structured Text syntax.
- String assignments are converted to Structured Text syntax if variable type can be identified.

### Usage
Call the script with an complete Automation Studio project folder as argument. The script will search for all `.ab` files in the folder and its subfolders and convert them to `.st` files. You can also call the script with a single `.ab` file as argument to convert only that file.

Example command line usage:
``` 
python ab_2_st_converter.py path/to/project_or_file
```

### Command-Line Options

The script supports various command-line switches to disable specific conversion functions. This can be useful when certain conversions are not desired or when you want to run conversions incrementally.

#### Disabling Conversion Functions

| Switch | Description |
|--------|-------------|
| `--no-manual` | Disable manual fix notices for unsupported keywords (GOTO, type casts) |
| `--no-comment` | Disable comment conversion (block comments `(* *)` to line comments `//`) |
| `--no-keywords` | Disable keyword replacements (e.g., `ENDIF` → `END_IF`) |
| `--no-uppercase` | Disable uppercase conversion for keywords (e.g., `true` → `TRUE`) |
| `--no-numbers` | Disable number format conversion (e.g., `$FF` → `16#FF`, `%1010` → `2#1010`) |
| `--no-select` | Disable SELECT/STATE/WHEN/NEXT to CASE transformation |
| `--no-case` | Disable CASE/ENDCASE action cleanup (ACTION/ENDACTION/ELSEACTION inside CASE blocks only) |
| `--no-loop` | Disable LOOP/ENDLOOP to FOR/END_FOR conversion |
| `--no-math` | Disable INC/DEC math function conversion |
| `--no-exitif` | Disable EXITIF to `IF...THEN...EXIT...END_IF` conversion |
| `--no-semicolon` | Disable automatic semicolon insertion at end of statements |
| `--no-functionblocks` | Disable function block syntax fix (FUB removal) |
| `--no-string-adr` | Disable conditional ADR wrapping for string assignments |
| `--no-string-adr-whitelist` | Disable ADR wrapping in whitelisted function arguments (strcpy, memcpy, etc.) |
| `--no-equals` | Disable `=` to `:=` assignment operator conversion |

#### Examples

Convert a project with all default conversions:
```
python ab_2_st_converter.py path/to/project
```

Convert a file but skip semicolon insertion and uppercase conversion:
```
python ab_2_st_converter.py path/to/file.ab --no-semicolon --no-uppercase
```

Convert a project but disable all string-related ADR conversions:
```
python ab_2_st_converter.py path/to/project --no-string-adr --no-string-adr-whitelist
```

Show help with all available options:
```
python ab_2_st_converter.py --help
```


### Edge case

There are a few Automation Basic constructs that can not be converted automatically to Structured Text. If the conversion script encounters these constructs, it will add a comment starting with ### CONVERSION ERROR ###. Search for these comments after conversion to identify code that requires manual intervention. Below is a list of known corner cases with an explanation and an example code snippet.

#### Inline function block calls
In Automation Basic you can call function blocks inline as part of an expression. For example:
```
TON(diff_err_pos,time,diff_str_pos,dif_pos);
```
This type of call is not supported in Structured Text. You have to create an instance of the function block and call it separately:
```
my_ton_instance(IN := diff_err_pos, PT := time);
dif_pos := my_ton_instance.Q;
```
Since the script can not determine the name of the function block instance during conversion, this code can not be converted automatically.

#### String conversion

In Automation Basic the address of a string and the string itself are interchangeable. For example, you can assign a string variable to another string variable like this:
```
str_value = 'Hello World'
```
The variable `str_value` can be of type STRING or of type UDINT. Both assignments are valid. Structure Text is more strict about types. You have to use the `ADR` function to get the address of a string:
```
str_value := 'Hello World';         // str_value must be of type STRING
udint_value := ADR('Hello World');  // udint_value must be of type UDINT
```

The script will try to identify the variable type and convert the code accordingly. However, if the variable type cannot be determined during conversion this code can not be converted automatically.

#### Variable casting

In Automation Basic you can cast variables by using the datatype as a function like this:
```
time_diff := REAL(fub_timebase)*1e-6;
```

In Structured Text you have to use a cast function that considers the datatype your converting from:
```
time_diff := DINT_TO_REAL(fub_timebase, REAL) * 1e-6;
```

Since the source datatype cannot be determined during conversion, this code can not be converted automatically.

#### Loop without condition

This code snippet can not be converted automatically. Use REPEAT...END_REPEAT or WHILE...END_WHILE instead.
```
loop
    exitif (X < param[i+2]) or (i>=((2*n)-4))
    i = i + 2
endloop
```

#### GOTO statements
GOTO statements are not supported in Structured Text. You have to refactor the code to use structured control flow instead.