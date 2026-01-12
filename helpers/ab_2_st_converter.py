import argparse
import os
import re
import sys
from pathlib import Path

# Ensure repository root is on sys.path so 'from utils import utils' works when
# this script is executed directly (e.g., from the helpers directory).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import utils

# Global configuration for enabled conversion functions (set by CLI arguments)
CONVERSION_CONFIG = {
    'manual': True,
    'comment': True,
    'keywords': True,
    'uppercase': True,
    'numbers': True,
    'select': True,
    'loop': True,
    'math': True,
    'exitif': True,
    'semicolon': True,
    'functionblocks': True,
    'string_adr': True,
    'string_adr_whitelist': True,
    'equals': True,
}

# Mapping of keywords to replace: 'old_word' -> 'new_word'.
# Edit this dict to include the keyword replacements you want applied to files.
KEYWORD_MANUAL_FIX: dict[str, str] = {
    'GOTO': '### CONVERSION ERROR ### Goto is not supported in structure text.',
    'TIME(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'BOOL(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'WORD(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'REAL(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'UDINT(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'UINT(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'USINT(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'SINT(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'DINT(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'INT(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'INT16(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'INT32(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'UINT16(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
    'UNT32(': '### CONVERSION ERROR ### The cast can not be automatically converted, determine the correct datatype and then use the convert library to cast the value.',
}

# Mapping of keywords to replace: 'old_word' -> 'new_word'.
# Edit this dict to include the keyword replacements you want applied to files.
KEYWORD_REPLACEMENTS: dict[str, str] = {
    '"': '\'',
    'ENDIF': 'END_IF',
    'ENDSELECT': 'END_CASE',
    'EXITIF TRUE': 'EXIT',
    'ELSE IF': 'ELSIF',
    'LSL(': 'SHL(',
    'LSR(': 'SHR(',
    'ACTION': '',
    'ENDACTION': '',
    'ELSEACTION': 'ELSE',
    'ENDCASE': 'END_CASE',
}

# List of keyword pairs (start, end) which define regions where '=' should NOT be
# converted to ':=' by `fix_equals`. Between a 'start' keyword and its corresponding
# 'end' keyword, no conversion happens - even across multiple lines.
IGNORE_EQUALS_PAIRS: list[tuple[str, str]] = [
    ('IF', 'THEN'),
    ('ELSIF', 'THEN'),
    ('WHILE', 'DO'),
    ('EXITIF', 'THEN'),  # EXITIF gets converted to IF...THEN later
]

IGNORE_SEMICOLON_KEYWORDS: list[str] = [
    'IF', 
    'THEN', 
    'ELSE',
    'ELSIF',
    'END_IF',
    'FOR',
    'END_FOR',
    'WHILE'
    'END_WHILE',
    'CASE',
    'END_CASE',
    '_INIT',
    '_EXIT',
    '_CYCLIC',
    '_PROGRAM',
    'END_PROGRAM',
    'FUNCTION_BLOCK',
    'END_FUNCTION_BLOCK',
    'FUNCTION',
    'END_FUNCTION',
]

MAKE_UPPER_CASE: list[str] = [
    'TRUE',
    'FALSE',
    'ACCESS',
    'MOD',
    'AND',
    'NOT',
    'IF',
    'THEN',
    'ELSE',
    'ELSIF',
    'END_IF',
    'FOR',
    'END_FOR',
    'WHILE',
    'END_WHILE',
    '_INIT',
    '_EXIT',
    '_CYCLIC',
    '_PROGRAM',
    'EDGE',
    'EDGEPOS',
    'EDGENEG',
    'ABS(',
    'ACOS(',
    'ADR(',
    'ADRINST(',
    'ASIN(',
    'ASR(',
    'ATAN(',
    'COS(',
    'EXP(',
    'EXPT(',
    'LIMIT(',
    'LN(',
    'LOG(',
    'MAX(',
    'MIN(',
    'MUX(',
    'ROL(',
    'ROR(',
    'SEL(',
    'SHL(',
    'SHR(',
    'SIN(',
    'SIZEOF(',
    'SQRT(',
    'TAN(',
    'TRUNC(',
    'DOWNTO',
    'DO',
    'OR',
    'TO',
    'XOR',
    'CASE',
    'OF',
]


# Functions whose string arguments may be converted to ADR('<...').
# Extensible: e.g. 'strcat', 'memcpy', 'sprintf', ...
STRING_TO_ADR_FUNC_WHITELIST: list[str] = [
    'strcpy',
    'strlen',
    'strcmp',
    'strcat',
    'brsstrcpy',
    'brsstrlen',
    'brsstrcmp',
    'brsstrcat',
    'memset',
    'memcpy',
    'memcmp',
]

def rename_file(file_path: Path) -> Path | None:
    # Adjust references in IEC.prg if it exists
    iec_file = file_path.parent / "IEC.prg"
    if not iec_file.exists():
        # Adjust references in IEC.lby if it exists
        iec_file = file_path.parent / "IEC.lby"
        if not iec_file.exists():
            return None

    text = iec_file.read_text(encoding="iso-8859-1")

    # Replace filename suffixes like 'name.ab' with 'name.st' (word boundary, case-insensitive)
    new_text, count = re.subn(r'(?i)(\b[\w/\\.-]+)\.ab\b', lambda m: m.group(1) + '.st', text)
    if count:
        iec_file.write_text(new_text, encoding="iso-8859-1")
        utils.log(f"{count} IEC references updated in: {iec_file}", severity="INFO")

    new_file_path = file_path.with_suffix('.st')
    if new_file_path != file_path:
        file_path.rename(new_file_path)
        utils.log(
            f"Renamed file: {file_path} to {new_file_path}",
            severity="INFO",
        )
    return new_file_path

def fix_comment(file_path: Path):
    """
    Fix comments by converting:
      - block comments that start with '(*' and end with '*)' into line comments starting with '//'
        * A line that starts with '(*' will have '(*' replaced by '//' on that line.
        * Subsequent lines that start with ' *' will have their leading ' *' replaced by '//'.
        * The closing line (contains '*)') will have '*)' removed and '//' added at the start.
      - and replace all ';' with '//' anywhere (legacy behavior).
    """
    original_hash = utils.calculate_file_hash(file_path)
    original_content = utils.read_file(file_path)

    lines = original_content.splitlines(keepends=True)
    new_lines: list[str] = []
    semicolon_replacements = 0
    block_replacements = 0
    in_block = False

    def split_line_ending(s: str) -> tuple[str, str]:
        """Return (content_without_linebreak, normalized_linebreak).

        Normalizes all line breaks to '\n' to avoid producing '\r\r\n' when writing
        on Windows (text-mode newline translation).
        """
        if s.endswith('\n'):
            content = s[:-1]
            if content.endswith('\r'):
                content = content[:-1]
            return content, '\n'
        if s.endswith('\r'):
            return s[:-1], '\n'
        return s, ''

    for i, line in enumerate(lines):
        new_line = line

        # Cleanup pass: if a blank line sits between two line-comments ('//'), drop it.
        # This fixes already-converted files that have an empty line between every comment line.
        if line.strip() == '':
            prev_line = new_lines[-1] if new_lines else ''
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            if re.match(r'^\s*//', prev_line) and re.match(r'^\s*//', next_line):
                continue

        # If the line already contains '//' anywhere, do not change it.
        # Still update block state if this is a closing block line.
        if '//' in line:
            if in_block and '*)' in line:
                in_block = False
            new_lines.append(line)
            continue

        if not in_block:
            # Split line ending from line content (CRLF/CR/LF-safe) and normalize to '\n'
            line_content, line_ending = split_line_ending(line)

            # Check if line starts a block comment
            m = re.match(r'^(\s*)\(\*(.*)$', line_content)
            if m:
                leading = m.group(1)
                rest_content = m.group(2)

                if '*)' in rest_content:
                    # Single-line block comment
                    idx = rest_content.find('*)')
                    content = rest_content[:idx]
                    suffix = rest_content[idx + 2:]
                    new_line = leading + '//' + content + suffix + line_ending
                    block_replacements += 1
                else:
                    # Multi-line block comment starts
                    new_line = leading + '//' + rest_content + line_ending
                    block_replacements += 1
                    in_block = True
            else:
                # Replace ';' when followed by text OR only whitespace to end-of-line
                new_line, n = re.subn(r';(?=\s*(?:\S|$))', r'//', new_line)
                semicolon_replacements += n

        else:
            # Inside block comment
            # Drop whitespace-only lines inside block comments.
            # This prevents CRCRLF artifacts (blank lines between every comment line).
            if line.strip() == '':
                continue

            # Check if this is the closing line
            if '*)' in line:
                # Closing line
                # Extract line ending
                line_content, line_ending = split_line_ending(line)
                
                # Find the leading whitespace
                m_leading = re.match(r'^(\s*)', line_content)
                leading_ws = m_leading.group(1) if m_leading else ''
                
                # Find the *)
                idx = line_content.find('*)')
                content_before_close = line_content[len(leading_ws):idx]
                content_after_close = line_content[idx+2:]
                
                # Remove leading * if present
                if content_before_close.lstrip().startswith('*'):
                    content_before_close = content_before_close.lstrip()[1:].lstrip()
                
                new_line = leading_ws + '//' + content_before_close + content_after_close + line_ending
                block_replacements += 1
                in_block = False
            else:
                # Regular line inside block comment
                # Extract line ending
                line_content, line_ending = split_line_ending(line)
                
                # Find the leading whitespace
                m_leading = re.match(r'^(\s*)', line_content)
                leading_ws = m_leading.group(1) if m_leading else ''
                rest = line_content[len(leading_ws):]
                
                # Remove leading * if present
                if rest.startswith('*'):
                    rest = rest[1:]
                    # Also remove one space after * if present
                    if rest.startswith(' '):
                        rest = rest[1:]
                
                new_line = leading_ws + '//' + rest + line_ending
                block_replacements += 1

        # Preserve legacy behavior: convert ';' to '//' only when it's followed by comment text
        new_line, n = re.subn(r';(?=\s*\S)', r'//', new_line)
        semicolon_replacements += n

        new_lines.append(new_line)

    modified_content = ''.join(new_lines)

    if modified_content != original_content:
        # Keep content normalized to '\n', but write as CRLF for Windows/AS compatibility.
        # This also avoids producing '\r\r\n' because our content contains no '\r'.
        file_path.write_text(modified_content, encoding="iso-8859-1", newline="\r\n")

        new_hash = utils.calculate_file_hash(file_path)
        if original_hash == new_hash:
            return

        total = semicolon_replacements + block_replacements
        utils.log(f"{total} comments changed in: {file_path}", severity="INFO")
        return

    return


def fix_manual(file_path: Path) -> int:
    """
    Insert manual-review comments for keywords defined in `KEYWORD_MANUAL_FIX`.
    For each line that contains a keyword (case-insensitive, word-boundary), a comment
    line is inserted *before* the line with the message from the mapping. The comment
    is indented to match the code line.
    Returns the number of inserted comments.
    """
    if not KEYWORD_MANUAL_FIX:
        return 0

    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0

    # Precompile case-insensitive word-boundary patterns for each keyword
    patterns = []
    for k, v in KEYWORD_MANUAL_FIX.items():
        if not k:
            continue
        # Only add trailing \b if keyword ends with a word character
        escaped = re.escape(k)
        if re.search(r'\w$', k):
            pat = re.compile(r"\b" + escaped + r"\b", flags=re.IGNORECASE)
        else:
            pat = re.compile(r"\b" + escaped, flags=re.IGNORECASE)
        patterns.append((k, pat, v))

    for line in lines:
        # Check each pattern; if matched, insert one comment block before the line
        matched_msg = None
        for k, pat, msg in patterns:
            if pat.search(line):
                matched_msg = msg
                break

        if matched_msg:
            # Avoid inserting duplicate if previous line already contains the same message
            if not (new_lines and new_lines[-1].strip().startswith("//") and matched_msg in new_lines[-1]):
                m_leading = re.match(r'^(\s*)', line)
                leading_ws = m_leading.group(1) if m_leading else ''
                for msg_line in matched_msg.splitlines():
                    new_lines.append(f"{leading_ws}// {msg_line}\n")
                total += 1

        new_lines.append(line)

    if total:
        file_path.write_text(''.join(new_lines), encoding='iso-8859-1')
        utils.log(f"{total} manual fix notices added in: {file_path}", severity="WARNING")

    return total


def fix_keywords(file_path: Path, replacements: dict[str, str] | None = None) -> int:
    """
    Replace keywords in the file according to `replacements` mapping (word-boundary matches).
    Returns the total number of replacements made.
    """
    if replacements is None:
        replacements = KEYWORD_REPLACEMENTS

    if not replacements:
        return 0

    original_content = utils.read_file(file_path)
    modified = original_content
    total_replacements = 0

    for old, new in replacements.items():
        if not old:
            continue
        # If the keyword contains at least one word character (letters/digits/underscore),
        # use word-boundary anchored, case-insensitive matching. Otherwise (punctuation-only
        # tokens like '"'), do a plain literal replacement so the token is found.
        if re.search(r"\w", old):
            pattern = r"\b" + re.escape(old) + r"\b"
            modified, count = re.subn(pattern, new, modified, flags=re.IGNORECASE)
        else:
            modified, count = re.subn(re.escape(old), new, modified)
        total_replacements += count

    if total_replacements:
        file_path.write_text(modified, encoding="iso-8859-1")
        utils.log(f"{total_replacements} keyword replacements in: {file_path}", severity="INFO")

    return total_replacements


def fix_upper_case(file_path: Path, keywords: list[str] | None = None) -> int:
    """
    Convert occurrences of keywords in `keywords` to upper-case (word-boundary, case-insensitive).
    Does not alter text inside line-comments starting with '//' (preserves comments as-is).
    Returns the number of actual changes made (only counts when text was actually modified).
    """
    if keywords is None:
        keywords = MAKE_UPPER_CASE

    if not keywords:
        return 0

    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0

    for line in lines:
        # Split line into code and comment parts (keep comment unchanged)
        idx = line.find('//')
        if idx != -1:
            code = line[:idx]
            comment = line[idx:]
        else:
            code = line
            comment = ''

        modified_code = code

        for kw in keywords:
            if not kw:
                continue
            # If the keyword begins or ends with whitespace, require whitespace there
            # (e.g., ' OR ' should only match when preceded and followed by spaces).
            if kw.startswith(' ') or kw.endswith(' '):
                left_look = r'(?<=\s)' if kw.startswith(' ') else ''
                right_look = r'(?=\s)' if kw.endswith(' ') else ''
                inner = re.escape(kw.strip())
                pattern = left_look + inner + right_look
                repl = kw.strip().upper()
                
                # Custom replacement that only counts actual changes
                def replace_func(match):
                    nonlocal total
                    original_text = match.group(0)
                    if original_text != repl:
                        total += 1
                    return repl
                
                modified_code = re.sub(pattern, replace_func, modified_code, flags=re.IGNORECASE)
            else:
                # Use lookarounds that prevent letters and digits before/after the keyword.
                # This allows parentheses, operators, spaces etc. but prevents matching
                # inside longer identifiers (e.g., 'COMMAND' should not match 'AND').
                # Only apply trailing lookahead when kw ends with a word char.
                if re.search(r'\w$', kw):
                    pattern = r'(?<![a-zA-Z0-9_])' + re.escape(kw) + r'(?![a-zA-Z0-9_])'
                else:
                    pattern = r'(?<![a-zA-Z0-9_])' + re.escape(kw)
                
                # Custom replacement that only counts actual changes
                def replace_func(match):
                    nonlocal total
                    original_text = match.group(0)
                    upper_text = kw.upper()
                    if original_text != upper_text:
                        total += 1
                    return upper_text
                
                modified_code = re.sub(pattern, replace_func, modified_code, flags=re.IGNORECASE)

        new_lines.append(modified_code + comment)

    if total:
        file_path.write_text(''.join(new_lines), encoding="iso-8859-1")
        utils.log(f"{total} upper-case replacements in: {file_path}", severity="INFO")

    return total


def fix_numbers(file_path: Path) -> int:
    """
    Replace hex numeric literals that use the `$` prefix (e.g. `$FF`) with the
    `16#FF` notation, and binary literals that use the `%` prefix (e.g. `%1010`) 
    with the `2#1010` notation. Uses word-boundary matching so trailing characters 
    are not accidentally captured. Returns number of replacements.
    """
    original = utils.read_file(file_path)
    total_count = 0
    
    # Match '$' followed by one or more hex digits, followed by a word boundary
    hex_pattern = r"\$([0-9A-Fa-f]+)\b"
    modified, hex_count = re.subn(hex_pattern, r"16#\1", original)
    total_count += hex_count
    
    # Match '%' followed by one or more binary digits, followed by a word boundary
    bin_pattern = r"%([01]+)\b"
    modified, bin_count = re.subn(bin_pattern, r"2#\1", modified)
    total_count += bin_count
    
    if total_count:
        file_path.write_text(modified, encoding="iso-8859-1")
        if hex_count and bin_count:
            utils.log(f"{hex_count} hex ($ -> 16#) and {bin_count} binary (% -> 2#) conversions in: {file_path}", severity="INFO")
        elif hex_count:
            utils.log(f"{hex_count} hex number conversions ($ -> 16#) in: {file_path}", severity="INFO")
        elif bin_count:
            utils.log(f"{bin_count} binary number conversions (% -> 2#) in: {file_path}", severity="INFO")
    return total_count


def fix_math_functions(file_path: Path) -> int:
    """
    Replace standalone INC(expr) with 'expr := expr + 1' and DEC(expr) with 'expr := expr - 1'.
    Only performs replacement when the INC/DEC is the only code on that line (ignoring trailing comments and spaces).
    Returns the number of replacements made.
    """
    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0

    inc_re = re.compile(r'^\s*INC\s*\(\s*([^\)]+?)\s*\)\s*;?\s*$', flags=re.IGNORECASE)
    dec_re = re.compile(r'^\s*DEC\s*\(\s*([^\)]+?)\s*\)\s*;?\s*$', flags=re.IGNORECASE)

    for line in lines:
        # preserve newline and split code/comment
        if line.endswith('\r\n'):
            newline = '\r\n'
            content = line[:-2]
        elif line.endswith('\n'):
            newline = '\n'
            content = line[:-1]
        else:
            newline = ''
            content = line

        idx = content.find('//')
        if idx != -1:
            code = content[:idx]
            comment = content[idx:]
        else:
            code = content
            comment = ''

        m_inc = inc_re.match(code)
        m_dec = dec_re.match(code)
        if m_inc:
            expr = m_inc.group(1).strip()
            m_ws = re.match(r'^(\s*)', code)
            leading_ws = m_ws.group(1) if m_ws else ''
            has_semicolon = code.rstrip().endswith(';')
            new_before = leading_ws + f"{expr} := {expr} + 1"
            if has_semicolon:
                new_before += ';'
            new_lines.append(new_before + ('' if comment == '' else ' ' + comment) + newline)
            total += 1
            continue
        if m_dec:
            expr = m_dec.group(1).strip()
            m_ws = re.match(r'^(\s*)', code)
            leading_ws = m_ws.group(1) if m_ws else ''
            has_semicolon = code.rstrip().endswith(';')
            new_before = leading_ws + f"{expr} := {expr} - 1"
            if has_semicolon:
                new_before += ';'
            new_lines.append(new_before + ('' if comment == '' else ' ' + comment) + newline)
            total += 1
            continue

        new_lines.append(line)

    if total:
        file_path.write_text(''.join(new_lines), encoding='iso-8859-1')
        utils.log(f"{total} INC/DEC conversions in: {file_path}", severity='INFO')

    return total


def fix_select(file_path: Path) -> int:
    """
    Transform SELECT/STATE/WHEN/NEXT patterns into CASE/labels/IF/assignment blocks.

    Robust rules (case-insensitive), preserving indentation and trailing text (comments '//' or '(*...*)',
    and semicolon order, in any arrangement:

    - SELECT value1        -> CASE value1 OF
    - STATE value2         -> value2:
    - WHEN condition       -> IF condition THEN
    - NEXT value4          -> value1 := value4;  (value1 is the last SELECT value)
      and add a following line with END_IF

    Returns total number of replacements. If at least one replacement happens,
    the file is rewritten in 'iso-8859-1'.
    """
    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)

    new_lines: list[str] = []
    total = 0
    current_select = None

    # Prefix detectors (capture indentation + keyword + minimal value/condition).
    # We compute and preserve the full "tail" of the line (the part after the captured token),
    # so the original order of comment/semicolon stays intact.
    sel_prefix = re.compile(r"^(\s*)SELECT\b\s+(\S+)", flags=re.IGNORECASE)
    state_prefix = re.compile(r"^(\s*)STATE\b\s+(\S+)", flags=re.IGNORECASE)
    next_prefix = re.compile(r"^(\s*)NEXT\b\s+(\S+)", flags=re.IGNORECASE)

    # WHEN can appear as 'WHEN(' or 'WHEN condition'. We match the prefix and then
    # split the line into condition + tail using a tail pattern that tolerates:
    #  - spaces
    #  - optional comment ('//...' or '(*...*)') in either position relative to ';'
    #  - optional semicolon
    when_prefix = re.compile(r"^(\s*)WHEN\b\s*", flags=re.IGNORECASE)
    tail_re = re.compile(r"\s*(?:(//.*|\(\*.*?\*\)))?\s*(;)?\s*$")

    for line in lines:
        # SELECT
        m = sel_prefix.match(line)
        if m:
            leading, sel = m.group(1), m.group(2)
            current_select = sel
            tail = line[m.end():].rstrip('\r\n')  # preserve everything after the matched token
            new_lines.append(f"{leading}CASE {sel} OF{tail}\n")
            total += 1
            continue

        # STATE
        m = state_prefix.match(line)
        if m:
            leading, state = m.group(1), m.group(2)
            tail = line[m.end():].rstrip('\r\n')
            new_lines.append(f"{leading}{state}:{tail}\n")
            total += 1
            continue

        # WHEN
        m = when_prefix.match(line)
        if m:
            leading = m.group(1)
            # Find tail at end-of-line to isolate condition while keeping original tail order intact.
            m_tail = tail_re.search(line)
            # If tail pattern found, split condition/tail by indices; else, whole rest is condition.
            tail_start = m_tail.start() if m_tail else len(line.rstrip('\n'))
            cond = line[m.end():tail_start].strip()
            tail = line[tail_start:].rstrip('\r\n') if m_tail else ""
            new_lines.append(f"{leading}IF {cond} THEN{tail}\n")
            total += 1
            continue

        # NEXT
        m = next_prefix.match(line)
        if m:
            leading, nxt = m.group(1), m.group(2)
            tail = line[m.end():].rstrip('\r\n')  # keep comment/semicolon order exactly
            if current_select:
                new_lines.append(f"{leading}{current_select} := {nxt}{tail}\n")
                new_lines.append(f"{leading}END_IF\n")
                total += 1
            else:
                # no SELECT in scope — leave unchanged
                new_lines.append(line)
            continue

        # default: keep line unchanged
        new_lines.append(line)

    if total:
        file_path.write_text(''.join(new_lines), encoding='iso-8859-1')
        utils.log(f"{total} SELECT/STATE/WHEN/NEXT transformations in: {file_path}", severity='INFO')

    return total

def fix_equals(file_path: Path, ignore_pairs: list[tuple[str, str]] | None = None) -> int:
    """
    Replace the FIRST single '=' with ':=' in each statement. A statement can span
    multiple lines and ends with ';'. Only the first '=' per statement is converted,
    all subsequent '=' are left unchanged (they are likely comparisons).
    
    Between keyword pairs (e.g., IF...THEN), no conversion happens - even across multiple lines.
    This handles multi-line conditions like:
        IF (a = 1) AND
           (b = 2) THEN
    
    Also ignores lines where the code ends with a backslash '\'.
    Returns number of replacements.
    """
    if ignore_pairs is None:
        ignore_pairs = IGNORE_EQUALS_PAIRS

    original_content = utils.read_file(file_path)
    
    # Build patterns for start and end keywords
    start_patterns: list[tuple[str, re.Pattern]] = []
    end_patterns: dict[str, re.Pattern] = {}
    for start_kw, end_kw in ignore_pairs:
        start_pat = re.compile(r'\b' + re.escape(start_kw) + r'\b', flags=re.IGNORECASE)
        end_pat = re.compile(r'\b' + re.escape(end_kw) + r'\b', flags=re.IGNORECASE)
        start_patterns.append((start_kw, start_pat))
        end_patterns[start_kw] = end_pat
    
    lines = original_content.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0
    
    # Track which ignore region we're in (None = not in any region)
    in_ignore_region: str | None = None
    
    # Track if we already replaced '=' in the current statement (across lines)
    # A statement ends with ';' or 'DO'
    replaced_in_statement = False
    
    # Pattern to find statement terminators: ';' or 'DO' (word boundary)
    statement_end_pattern = re.compile(r';|\bDO\b', flags=re.IGNORECASE)
    
    def find_statement_end(text: str, start_pos: int) -> tuple[int, int] | None:
        """Find the next statement terminator (';' or 'DO') in text starting at start_pos.
        Returns (start_index, end_index) of the match, or None if not found."""
        match = statement_end_pattern.search(text, start_pos)
        if match:
            return (match.start(), match.end())
        return None

    for line in lines:
        # Determine original line ending
        if line.endswith('\r\n'):
            line_ending = '\r\n'
        elif line.endswith('\n'):
            line_ending = '\n'
        else:
            line_ending = ''
        
        # Remove line ending for processing
        line_content = line.rstrip('\r\n')
        
        # Split line into code and comment parts
        idx = line_content.find('//')
        if idx != -1:
            code = line_content[:idx]
            comment = line_content[idx:]
        else:
            code = line_content
            comment = ''
        
        # Check if code ends with backslash (line continuation)
        if code.rstrip().endswith('\\'):
            new_lines.append(line)
            continue
        
        # Process code character by character, tracking ignore regions and statements
        new_code = ''
        pos = 0
        
        while pos < len(code):
            # If we're in an ignore region, look for the end keyword
            if in_ignore_region is not None:
                end_pat = end_patterns[in_ignore_region]
                end_match = end_pat.search(code, pos)
                if end_match:
                    # Found end keyword - copy everything up to and including it
                    new_code += code[pos:end_match.end()]
                    pos = end_match.end()
                    in_ignore_region = None
                else:
                    # End keyword not on this line - copy rest of line unchanged
                    new_code += code[pos:]
                    break
            else:
                # Not in ignore region - look for start keywords and statement terminators
                earliest_start = None
                earliest_pos = len(code)
                earliest_kw = None
                
                for start_kw, start_pat in start_patterns:
                    start_match = start_pat.search(code, pos)
                    if start_match and start_match.start() < earliest_pos:
                        earliest_start = start_match
                        earliest_pos = start_match.start()
                        earliest_kw = start_kw
                
                # Also look for statement end (';' or 'DO')
                stmt_end = find_statement_end(code, pos)
                stmt_end_pos = stmt_end[0] if stmt_end else -1
                
                if earliest_start and (stmt_end_pos == -1 or earliest_start.start() < stmt_end_pos):
                    # Start keyword comes before statement end (or no statement end)
                    # Process code before the start keyword (replace first = with := if not done yet)
                    before = code[pos:earliest_start.start()]
                    
                    # Check for statement terminators in the 'before' section
                    stmt_end_in_before = find_statement_end(before, 0)
                    if stmt_end_in_before:
                        # Process up to and including terminator
                        before_term = before[:stmt_end_in_before[1]]
                        after_term = before[stmt_end_in_before[1]:]
                        
                        if not replaced_in_statement:
                            replaced, n = re.subn(r'(?<![:=<>])=(?!=)', ':=', before_term, count=1)
                            if n > 0:
                                replaced_in_statement = True
                                total += n
                            new_code += replaced
                        else:
                            new_code += before_term
                        
                        # Reset for new statement
                        replaced_in_statement = False
                        
                        # Process rest after terminator
                        if not replaced_in_statement:
                            replaced, n = re.subn(r'(?<![:=<>])=(?!=)', ':=', after_term, count=1)
                            if n > 0:
                                replaced_in_statement = True
                                total += n
                            new_code += replaced
                        else:
                            new_code += after_term
                    else:
                        if not replaced_in_statement:
                            replaced, n = re.subn(r'(?<![:=<>])=(?!=)', ':=', before, count=1)
                            if n > 0:
                                replaced_in_statement = True
                                total += n
                            new_code += replaced
                        else:
                            new_code += before
                    
                    # Add the start keyword itself
                    new_code += code[earliest_start.start():earliest_start.end()]
                    pos = earliest_start.end()
                    
                    # Check if end keyword is on the same line after start
                    assert earliest_kw is not None  # guaranteed by the if-condition above
                    end_pat = end_patterns[earliest_kw]
                    end_match = end_pat.search(code, pos)
                    if end_match:
                        # End keyword found on same line - copy up to and including it
                        new_code += code[pos:end_match.end()]
                        pos = end_match.end()
                        # Stay outside ignore region
                    else:
                        # End keyword not on this line - enter ignore region
                        in_ignore_region = earliest_kw
                        new_code += code[pos:]
                        break
                elif stmt_end:
                    # Statement end comes first - process up to and including it
                    before_term = code[pos:stmt_end[1]]
                    
                    if not replaced_in_statement:
                        replaced, n = re.subn(r'(?<![:=<>])=(?!=)', ':=', before_term, count=1)
                        if n > 0:
                            replaced_in_statement = True
                            total += n
                        new_code += replaced
                    else:
                        new_code += before_term
                    
                    # Reset for new statement after terminator
                    replaced_in_statement = False
                    pos = stmt_end[1]
                else:
                    # No start keyword and no statement end - process rest of line
                    rest = code[pos:]
                    if not replaced_in_statement:
                        replaced, n = re.subn(r'(?<![:=<>])=(?!=)', ':=', rest, count=1)
                        if n > 0:
                            replaced_in_statement = True
                            total += n
                        new_code += replaced
                    else:
                        new_code += rest
                    break
        
        # Reconstruct the line with original line ending
        new_line = new_code + comment + line_ending
        new_lines.append(new_line)

    if total:
        file_path.write_text(''.join(new_lines), encoding="iso-8859-1")
        utils.log(f"{total} equals replaced by ':=' in: {file_path}", severity="INFO")

    return total


from pathlib import Path
import re

def fix_semicolon(file_path: Path, ignore_keywords: list[str] | None = None) -> int:
    """
    Add ';' at the end of each non-empty code line. If a line contains an inline
    '//' comment, insert ';' right after the code and before the comment (preserve
    any spaces between code and comment). Ignore lines that start with '//' and
    contain any of `ignore_keywords` (word-boundary matches).

    Additionally:
    - Detect and remove a trailing '\' at the end of the *code part* (before any '//' comment),
      even on lines that match ignore_keywords (so control-structure lines are cleaned).
    - If a trailing '\' was detected on a line, do NOT add a semicolon to that line.

    Returns number of semicolons added.
    """
    if ignore_keywords is None:
        ignore_keywords = IGNORE_SEMICOLON_KEYWORDS

    ignore_pattern = None
    if ignore_keywords:
        pattern = r"\b(" + "|".join(re.escape(k) for k in ignore_keywords) + r")\b"
        ignore_pattern = re.compile(pattern, flags=re.IGNORECASE)

    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0

    def remove_trailing_backslash(code_part: str) -> tuple[str, bool]:
        """
        Remove a single trailing backslash from the code part (ignoring trailing spaces).
        Returns (new_code_part, had_backslash).
        """
        s = code_part.rstrip()
        had_backslash = s.endswith('\\')
        if had_backslash:
            s = s[:-1].rstrip()
        return s, had_backslash

    for line in lines:
        stripped = line.lstrip()
        # Skip completely empty lines (contain only whitespace/newline)
        if stripped == '':
            new_lines.append(line)
            continue

        # Pure comment lines (start with //) stay unchanged
        if stripped.startswith('//'):
            new_lines.append(line)
            continue

        # Split into code and comment parts
        idx = line.find('//')
        if idx != -1:
            before = line[:idx]
            comment = line[idx:]
            code_only_raw = before.rstrip()
            trailing_spaces = before[len(code_only_raw):]

            # NEW: detect & remove trailing backslash BEFORE ignore check
            code_only, had_backslash = remove_trailing_backslash(code_only_raw)

            # If the line matches ignore keywords -> do not add ';', but backslash is removed
            if ignore_pattern and ignore_pattern.search(line):
                new_lines.append(code_only + trailing_spaces + comment)
                continue

            # Semicolon logic:
            # If a trailing '\' was detected, do NOT add ';'
            if code_only == '' or code_only.endswith(';') or code_only.endswith(':') or had_backslash:
                new_before = code_only + trailing_spaces
            else:
                new_before = code_only + ';' + trailing_spaces
                total += 1

            new_lines.append(new_before + comment)

        else:
            # No inline comment — preserve newline
            if line.endswith('\r\n'):
                newline = '\r\n'; content_raw = line[:-2]
            elif line.endswith('\n'):
                newline = '\n'; content_raw = line[:-1]
            else:
                newline = ''; content_raw = line

            # NEW: detect & remove trailing backslash BEFORE ignore check
            content, had_backslash = remove_trailing_backslash(content_raw)

            # If the line matches ignore keywords -> do not add ';', but backslash is removed
            if ignore_pattern and ignore_pattern.search(line):
                new_lines.append(content + newline)
                continue

            # Semicolon logic:
            # If a trailing '\' was detected, do NOT add ';'
            if content.strip() == '' or content.endswith(';') or content.endswith(':') or had_backslash:
                new_lines.append(content + newline)
            else:
                new_lines.append(content.rstrip() + ';' + newline)
                total += 1

    # Build final content and remove any trailing whitespace at EOF
    content = ''.join(new_lines)
    trimmed = content.rstrip()
    content_to_write = trimmed

    if content_to_write != original:
        file_path.write_text(content_to_write, encoding="iso-8859-1")
        utils.log(f"{total} semicolons added in: {file_path}", severity="INFO")
        if content != content_to_write:
            utils.log(f"Trailing whitespace removed from end of file: {file_path}", severity="INFO")

    return total


def fix_functionblocks(file_path: Path) -> int:
    """
    Searches (case-insensitive) for ' FUB ' in the code part of a line.
    Removes everything from ' FUB ' onwards and appends '();' at the end of the remaining code.
    Existing end-of-line comments (// ...) remain unchanged.
    Returns the number of modified lines.
    """
    original_content = utils.read_file(file_path)
    lines = original_content.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0

    for line in lines:
        # Remember original line ending
        if line.endswith('\r\n'):
            newline = '\r\n'
            base = line[:-2]
        elif line.endswith('\n'):
            newline = '\n'
            base = line[:-1]
        else:
            newline = ''
            base = line

        # Separate code and comment parts
        idx_comment = base.find('//')
        if idx_comment != -1:
            code = base[:idx_comment]
            comment = base[idx_comment:]  # contains no newline; we add it back below
        else:
            code = base
            comment = ''

        # Search for exactly " FUB " (with spaces around it), case-insensitive, only in the code part
        m = re.search(r' FUB ', code, flags=re.IGNORECASE)
        if m:
            # Remove everything from the found position onwards
            new_code = code[:m.start()].rstrip()

            # Always append '();' if the code is not empty and doesn't already end with '();'
            if new_code and not new_code.endswith('();'):
                new_code = new_code + '();'

            # Reassemble the line; comment remains unchanged
            spacer = ' ' if new_code and comment else ''
            new_line = new_code + spacer + comment + newline
            new_lines.append(new_line)
            total += 1
        else:
            # Keep unchanged
            new_lines.append(line)

    if total:
        file_path.write_text(''.join(new_lines), encoding='iso-8859-1')
        utils.log(f"{total} lines updated by fix_functionblocks in: {file_path}", severity="INFO")

    return total

def fix_string_assignment_conditional_adr(file_path: Path) -> int:
    """
    Detects direct assignments of a plain single-quoted string:
        var := '...';
    and conditionally wraps the RHS with ADR('...') based on the variable type
    discovered in sibling .var/.fun files located in the same directory.

    Rules:
      - If the variable is found on a line containing 'STRING' (case-insensitive): do NOT modify.
      - If the variable is found on a line containing 'UDINT' (case-insensitive): wrap RHS with ADR('...').
      - If the variable is not found in .var/.fun OR found but neither 'STRING' nor 'UDINT' is present:
          insert a warning comment line before the code:
          "### CONVERSION WARNING ### The data type of the variable could not be determined.
           Make sure the variable is of type STRING or add ADR(...) if necessary."

    Preserves indentation, spacing, semicolons, and trailing '//' comments.
    Returns the number of modified lines (including inserted warnings).
    """
    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0

    # Match a direct assignment with a plain ST single-quoted string on the RHS.
    # This does NOT match lines that already have ADR(...), concatenations, etc.
    # Groups:
    #   leading: indentation
    #   lhs: left-hand side up to ':='
    #   ws: whitespace after ':=' (preserve)
    #   string: the ST string literal (supports '' escaping)
    #   tail: optional spaces and optional semicolon
    assign_re = re.compile(
        r"""^(?P<leading>\s*)
            (?P<lhs>.*?:=)
            (?P<ws>\s*)
            (?!ADR\s*\()                 # ensure ADR( is NOT already present
            (?P<string>'(?:[^']|'')*')   # ST single-quoted literal
            (?P<tail>\s*;?)\s*$""",
        re.VERBOSE,
    )

    # Extract base variable token from LHS (first identifier before any '.', '[', '(' ...)
    base_var_re = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)")

    # Helpers to determine type by scanning .var/.fun in the same directory
    def determine_var_type(var_name: str, folder: Path):
        """
        Scan .var and .fun files in 'folder' for lines containing the variable token (word-boundary).
        Returns a tuple: (found_any, is_string, is_udint)
        """
        found_any = False
        is_string = False
        is_udint = False

        # Build a word-boundary search for the variable name (case-insensitive)
        var_pat = re.compile(rf"\b{re.escape(var_name)}\b", flags=re.IGNORECASE)

        for ext in ("*.var", "*.fun"):
            for fp in folder.glob(ext):
                try:
                    content = utils.read_file(fp)
                except Exception:
                    # If utils.read_file fails on a particular file, skip it safely
                    continue

                # Check line by line (so we only look at the same line where the variable is mentioned)
                for line in content.splitlines():
                    if var_pat.search(line):
                        found_any = True
                        # Case-insensitive checks for type indicators on the SAME line
                        if re.search(r"\bSTRING\b", line, flags=re.IGNORECASE):
                            is_string = True
                        if re.search(r"\bUDINT\b", line, flags=re.IGNORECASE):
                            is_udint = True
                        # If both are seen somewhere, STRING takes precedence to "do not modify"
                        # but we don't early-return to collect all evidence.
        return found_any, is_string, is_udint

    for line in lines:
        # Preserve newline exactly
        if line.endswith('\r\n'):
            newline = '\r\n'; base = line[:-2]
        elif line.endswith('\n'):
            newline = '\n'; base = line[:-1]
        else:
            newline = ''; base = line

        # Split code from trailing comment
        idx_comment = base.find('//')
        if idx_comment != -1:
            code = base[:idx_comment]
            comment = base[idx_comment:]
        else:
            code = base
            comment = ''

        m = assign_re.match(code)
        if not m:
            # Not a direct string assignment -> pass through unchanged
            new_lines.append(line)
            continue

        leading = m.group('leading')
        lhs = m.group('lhs')       # includes everything up to ':='
        ws = m.group('ws')         # whitespace after ':='
        s_lit = m.group('string')  # the quoted string
        tail = m.group('tail')     # spaces and optional semicolon

        # Determine the base variable token for lookup
        m_base = base_var_re.match(lhs)
        if not m_base:
            # If we cannot extract a variable token, conservatively add a warning and keep the code unchanged.
            warn = f'{leading}// ### CONVERSION WARNING ### The data type of the variable could not be determined. Make sure the variable is of type STRING or add ADR(...) if necessary.{newline}'
            new_lines.append(warn)
            new_lines.append(line)
            total += 1
            continue

        var_token = m_base.group(1)

        # Scan sibling .var/.fun files in the same directory
        found_any, is_string, is_udint = determine_var_type(var_token, file_path.parent)

        if is_string:
            # Variable is STRING -> leave code unchanged
            new_lines.append(line)
            continue

        if is_udint:
            # Variable is UDINT -> wrap RHS with ADR('...')
            new_code = f"{leading}{lhs}{ws}ADR({s_lit}){tail}"
            spacer = '' if (not comment or new_code.endswith(' ')) else ' '
            new_lines.append(new_code + spacer + comment + newline)
            total += 1
            continue

        # Not found or type not determinable from the same line -> insert warning before the line
        warn = f'{leading}// ### CONVERSION WARNING ### The data type of the variable could not be determined. Make sure the variable is of type STRING or add ADR(...) if necessary.{newline}'
        new_lines.append(warn)
        new_lines.append(line)
        total += 1

    if total:
        file_path.write_text(''.join(new_lines), encoding='iso-8859-1')
        utils.log(f"{total} conditional ADR conversions/warnings in: {file_path}", severity='INFO')

    return total

def fix_string_to_adr_in_whitelisted_funcs(file_path: Path, func_whitelist: list[str] | None = None) -> int:
    """
    Converts ALL string literals ('...') in the argument lists of whitelisted functions
    to ADR('...'), unless ADR('...') is already present.
    - Independent of .var/.fun type checking.
    - Preserves indentation, spacing, semicolons, and end-of-line comments (// ...).

    Notes:
    - The conversion is performed specifically within the parentheses of whitelisted functions.
    - Strings that are already ADR('...') remain unchanged.
    - Strings in nested expressions within arguments are only converted when they appear
      directly at an argument boundary (beginning of argument list or after a comma).
      This minimizes unintended replacements in complex expressions.

    Returns: Number of modified lines.
    """
    if func_whitelist is None:
        func_whitelist = STRING_TO_ADR_FUNC_WHITELIST

    if not func_whitelist:
        return 0

    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0

    # Pattern to find function calls from the whitelist:  funcName(
    func_name_pat = re.compile(
        r"\b(" + "|".join(map(re.escape, func_whitelist)) + r")\s*\(",
        flags=re.IGNORECASE,
    )

    # Substitution within a single argument list:
    # - converts string literals at argument boundaries (beginning or after comma),
    #   unless ADR( is directly before it.
    def convert_args_substring(arg_substr: str) -> str:
        # Replace: (^|,)\s*(?!ADR\s*\() '...'
        # -> (^|,) ADR('...')
        return re.sub(
            r"(^|,)\s*(?!ADR\s*\()('(?:[^']|'')*')",
            lambda m: f"{m.group(1)} ADR({m.group(2)})",
            arg_substr,
            flags=re.IGNORECASE | re.MULTILINE,
        )

    for line in lines:
        # Separate newline
        if line.endswith('\r\n'):
            newline = '\r\n'; base = line[:-2]
        elif line.endswith('\n'):
            newline = '\n'; base = line[:-1]
        else:
            newline = ''; base = line

        # Separate code vs. comment (comment remains unchanged)
        idx = base.find('//')
        if idx != -1:
            code = base[:idx]
            comment = base[idx:]
        else:
            code = base
            comment = ''

        changed_line = False
        new_code = code
        pos = 0

        # Handle multiple function calls in one line sequentially
        while True:
            m = func_name_pat.search(new_code, pos)
            if not m:
                break

            func_start = m.start()
            paren_open = m.end() - 1  # Position of '('

            # Find the corresponding closing parenthesis ')'
            # taking nested parentheses into account.
            depth = 0
            i = paren_open
            end = None
            while i < len(new_code):
                ch = new_code[i]
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
                # Note: No string/comment internal handling here,
                # as we only replace argument boundaries via regex.
                i += 1

            if end is None:
                # Parentheses not balanced -> abort for this line
                break

            # Extract argument list (without outer parentheses)
            args_start = paren_open + 1
            args_end = end
            args = new_code[args_start:args_end]

            # Substitution in the argument list
            converted_args = convert_args_substring(args)

            if converted_args != args:
                # Assemble new code line
                new_code = new_code[:args_start] + converted_args + new_code[args_end:]
                changed_line = True
                # Set pos beyond the end of this function call,
                # to find subsequent calls in the same line
                pos = args_end  # safe: continue searching after this
            else:
                # Nothing changed -> search for the next call
                pos = end + 1

        if changed_line:
            total += 1
            spacer = '' if (not comment or new_code.endswith(' ')) else ' '
            new_lines.append(new_code + spacer + comment + newline)
        else:
            new_lines.append(line)

    if total:
        file_path.write_text(''.join(new_lines), encoding='iso-8859-1')
        utils.log(f"{total} ADR conversions for whitelisted function arguments in: {file_path}", severity="INFO")

    return total

def fix_exitif(file_path: Path) -> int:
    """
    Rewrites lines of the form:
        EXITIF <condition> [;] [// comment]
    into exactly:
        IF <condition> THEN     EXIT;END_IF [// comment]

    - Case-insensitive match for 'EXITIF'
    - Preserves original indentation and end-of-line comment
    - Preserves newline characters
    - Returns number of lines modified
    """
    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    total = 0

    # Matches: <indent> EXITIF <cond> [;] (no other code on the line)
    # The condition is captured as minimal '.*?' up to optional trailing ';' and spaces.
    pattern = re.compile(
        r"""^(?P<indent>\s*)         # leading whitespace
             EXITIF\b                # keyword (case-insensitive)
             (?P<ws>\s*)             # spaces after keyword
             (?P<cond>.+?)           # condition (non-greedy)
             \s*;?\s*$               # optional semicolon and trailing spaces
        """,
        re.IGNORECASE | re.VERBOSE
    )

    for line in lines:
        # Keep exact newline
        if line.endswith('\r\n'):
            newline = '\r\n'
            base = line[:-2]
        elif line.endswith('\n'):
            newline = '\n'
            base = line[:-1]
        else:
            newline = ''
            base = line

        # Split code vs trailing comment (comment remains unchanged)
        cidx = base.find('//')
        if cidx != -1:
            code = base[:cidx]
            comment = base[cidx:]   # includes the '//' prefix
        else:
            code = base
            comment = ''

        m = pattern.match(code)
        if not m:
            new_lines.append(line)
            continue

        indent = m.group('indent')
        cond = (m.group('cond') or '').strip()

        # Build the single-line replacement EXACTLY as requested
        new_code = f"{indent}IF {cond} THEN\r\n     EXIT;\r\nEND_IF"

        # Reassemble with original comment and newline
        spacer = '' if (not comment or new_code.endswith(' ')) else ' '
        new_lines.append(new_code + spacer + comment + newline)
        total += 1

    if total:
        file_path.write_text(''.join(new_lines), encoding="iso-8859-1")
        utils.log(f"{total} EXITIF rewrites to 'IF ... THEN' in: {file_path}", severity="INFO")

    return total


from pathlib import Path
import re

def fix_loop(file_path: Path) -> int:
    """
    Searches for 'LOOP' and replaces it with 'FOR', as well as 'ENDLOOP' with 'END_FOR'.
    Special case: If no further code follows 'LOOP' (only whitespace, ';' or '\'),
    the line remains unchanged, but a warning comment is inserted BEFORE the line:

      // ### CONVERSION ERROR ### This code snippet can not be converted automatically.
      // Use REPEAT...END_REPEAT or WHILE...END_WHILE instead.

    Comments are not modified. Returns the number of changes made
    (replacements + inserted comment lines).
    """
    original = utils.read_file(file_path)
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    conversions = 0
    warnings = 0

    # Word-boundary-aware, case-insensitive patterns
    re_loop_word = re.compile(r"\bLOOP\b", flags=re.IGNORECASE)
    re_endloop_word = re.compile(r"\bENDLOOP\b", flags=re.IGNORECASE)
    # Anchored 'LOOP' at the start of the code part
    re_loop_at_start = re.compile(r"^(\s*)LOOP\b", flags=re.IGNORECASE)
    # Only whitespace / ';' / '\' after?
    re_only_trivia_after_loop = re.compile(r"^[\s;\\]*$")

    warn_text = "### CONVERSION ERROR ### This code snippet can not be converted automatically. Use REPEAT...END_REPEAT or WHILE...END_WHILE instead."

    for line in lines:
        # Preserve newline
        if line.endswith('\r\n'):
            newline = '\r\n'; base = line[:-2]
        elif line.endswith('\n'):
            newline = '\n'; base = line[:-1]
        else:
            newline = ''; base = line

        # Separate code vs. comment
        idx = base.find('//')
        if idx != -1:
            code = base[:idx]
            comment = base[idx:]  # Comment remains unchanged
        else:
            code = base
            comment = ''

        # Check special case: 'LOOP' at the start of the line (in code part)
        m_start = re_loop_at_start.match(code)
        if m_start:
            tail = code[m_start.end():]
            if re_only_trivia_after_loop.match(tail):
                # Only whitespace/';'/'\' after LOOP -> do not convert, insert comment line before
                indent = m_start.group(1) or ""
                new_lines.append(f"{indent}// {warn_text}{newline}")
                new_lines.append(line)  # Original line unchanged
                warnings += 1
                continue  # Next line

        # Otherwise normal replacements in code part (comments remain)
        new_code = code

        # ENDLOOP -> END_FOR
        new_code, c1 = re_endloop_word.subn("END_FOR", new_code)
        # LOOP -> FOR (if present and not the special case above)
        new_code, c2 = re_loop_word.subn("FOR", new_code)
        
        # If the line contains LOOP (now FOR), also replace DOWNTO with TO
        if c2 > 0:
            new_code = re.sub(r'\bDOWNTO\b', 'TO', new_code, flags=re.IGNORECASE)

        if c1 + c2 > 0:
            conversions += (c1 + c2)
            new_lines.append(new_code + comment + newline)
        else:
            new_lines.append(line)

    total_changes = conversions + warnings
    if total_changes:
        file_path.write_text(''.join(new_lines), encoding="iso-8859-1")
        utils.log(
            f"{conversions} LOOP/ENDLOOP conversions, {warnings} warnings inserted in: {file_path}",
            severity="INFO"
        )

    return total_changes

def process_file(file_path: Path) -> int:
    """Process a single .ab or .st file through all conversion functions.
    Returns the total number of changes made."""
    total_changes = 0
    
    # Log separator line before each file
    utils.log("─" * 80, severity="INFO")
    utils.log(f"Processing: {file_path}", severity="INFO")
    
    # If it's a .ab file, rename it first
    if file_path.suffix == ".ab":
        new_path = rename_file(file_path)
        if new_path is None:
            utils.log(f"IEC.prg or IEC.lby not found in directory: {file_path.parent}", severity="ERROR")
            return 0
    else:
        new_path = file_path
    
    # Apply all conversion functions and sum up changes (respecting configuration)
    if CONVERSION_CONFIG['manual']:
        total_changes += fix_manual(new_path)
    if CONVERSION_CONFIG['comment']:
        total_changes += fix_comment(new_path) or 0
    if CONVERSION_CONFIG['keywords']:
        total_changes += fix_keywords(new_path)
    if CONVERSION_CONFIG['uppercase']:
        total_changes += fix_upper_case(new_path)
    if CONVERSION_CONFIG['numbers']:
        total_changes += fix_numbers(new_path)
    if CONVERSION_CONFIG['select']:
        total_changes += fix_select(new_path)
    if CONVERSION_CONFIG['loop']:
        total_changes += fix_loop(new_path)
    if CONVERSION_CONFIG['math']:
        total_changes += fix_math_functions(new_path)
    if CONVERSION_CONFIG['exitif']:
        total_changes += fix_exitif(new_path)
    if CONVERSION_CONFIG['semicolon']:
        total_changes += fix_semicolon(new_path)
    if CONVERSION_CONFIG['functionblocks']:
        total_changes += fix_functionblocks(new_path)
    if CONVERSION_CONFIG['string_adr']:
        total_changes += fix_string_assignment_conditional_adr(new_path)
    if CONVERSION_CONFIG['string_adr_whitelist']:
        total_changes += fix_string_to_adr_in_whitelisted_funcs(new_path)
    if CONVERSION_CONFIG['equals']:
        total_changes += fix_equals(new_path)
    
    return total_changes

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert Automation Basic (.ab) files to Structured Text (.st)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""

Examples:
  python ab_2_st_converter.py /path/to/project
  python ab_2_st_converter.py /path/to/file.ab --no-semicolon --no-uppercase
  python ab_2_st_converter.py . --no-string-adr --no-string-adr-whitelist
"""
    )
    
    parser.add_argument(
        'path',
        nargs='?',
        default=os.getcwd(),
        help='Path to the project directory or a single .ab file (default: current directory)'
    )
    
    # Add arguments to disable each conversion function
    parser.add_argument('--no-manual', action='store_true',
                        help='Disable manual fix notices insertion')
    parser.add_argument('--no-comment', action='store_true',
                        help='Disable comment conversion')
    parser.add_argument('--no-keywords', action='store_true',
                        help='Disable keyword replacements')
    parser.add_argument('--no-uppercase', action='store_true',
                        help='Disable uppercase conversion')
    parser.add_argument('--no-numbers', action='store_true',
                        help='Disable number format conversion')
    parser.add_argument('--no-select', action='store_true',
                        help='Disable SELECT/STATE/WHEN/NEXT transformation')
    parser.add_argument('--no-loop', action='store_true',
                        help='Disable LOOP/ENDLOOP conversion')
    parser.add_argument('--no-math', action='store_true',
                        help='Disable INC/DEC conversion')
    parser.add_argument('--no-exitif', action='store_true',
                        help='Disable EXITIF conversion')
    parser.add_argument('--no-semicolon', action='store_true',
                        help='Disable semicolon insertion')
    parser.add_argument('--no-functionblocks', action='store_true',
                        help='Disable function block syntax fix')
    parser.add_argument('--no-string-adr', action='store_true',
                        help='Disable conditional ADR wrapping for string assignments')
    parser.add_argument('--no-string-adr-whitelist', action='store_true',
                        help='Disable ADR wrapping in whitelisted function arguments')
    parser.add_argument('--no-equals', action='store_true',
                        help='Disable equals to assignment conversion')
    
    return parser.parse_args()


def apply_config_from_args(args):
    """Apply configuration from parsed arguments to CONVERSION_CONFIG."""
    global CONVERSION_CONFIG
    
    CONVERSION_CONFIG['manual'] = not args.no_manual
    CONVERSION_CONFIG['comment'] = not args.no_comment
    CONVERSION_CONFIG['keywords'] = not args.no_keywords
    CONVERSION_CONFIG['uppercase'] = not args.no_uppercase
    CONVERSION_CONFIG['numbers'] = not args.no_numbers
    CONVERSION_CONFIG['select'] = not args.no_select
    CONVERSION_CONFIG['loop'] = not args.no_loop
    CONVERSION_CONFIG['math'] = not args.no_math
    CONVERSION_CONFIG['exitif'] = not args.no_exitif
    CONVERSION_CONFIG['semicolon'] = not args.no_semicolon
    CONVERSION_CONFIG['functionblocks'] = not args.no_functionblocks
    CONVERSION_CONFIG['string_adr'] = not args.no_string_adr
    CONVERSION_CONFIG['string_adr_whitelist'] = not args.no_string_adr_whitelist
    CONVERSION_CONFIG['equals'] = not args.no_equals
    
    # Log disabled conversions
    disabled = [k for k, v in CONVERSION_CONFIG.items() if not v]
    if disabled:
        utils.log(f"Disabled conversions: {', '.join(disabled)}", severity="INFO")


def main():
    args = parse_arguments()
    apply_config_from_args(args)
    
    input_path = Path(args.path)
    
    # Check if input is a file or directory
    if input_path.is_file():
        # Single file mode
        if input_path.suffix not in {".ab"}:
            utils.log(f"Error: File must be .ab, got: {input_path.suffix}", severity="ERROR")
            return
        
        utils.log(f"Processing single file: {input_path}", severity="INFO")
        utils.log(
            "Before proceeding, make sure you have a backup or are using version control (e.g., Git).",
            severity="WARNING",
        )
        total = process_file(input_path)
        utils.log(f"File processing complete. Total changes: {total}", severity="INFO")
        
    elif input_path.is_dir():
        # Directory mode
        project_path = input_path
        apj_file = utils.get_and_check_project_file(project_path)

        utils.log(f"Project path validated: {project_path}")
        utils.log(f"Using project file: {apj_file}\n")

        utils.log(
            "This script will convert all Automation Basic tasks into Structure Text tasks.",
            severity="INFO",
        )
        utils.log(
            "Before proceeding, make sure you have a backup or are using version control (e.g., Git).",
            severity="WARNING",
        )

        proceed = utils.ask_user(
            "This script will convert all Automation Basic tasks into Structure Text tasks. Do you want to proceed with converting anyway? (y/n) [y]: ",
            extra_note="Note:",
        )

        if proceed != "y":
            utils.log("Operation cancelled. No changes were made.", severity="WARNING")
            return

        logical_path = project_path / "Logical"

        # Loop through the files in the "Logical" directory and process .ab files
        total_changes = 0
        files_processed = 0
        for file_path in logical_path.rglob("*"):
            if file_path.suffix in {".ab"}:
                total_changes += process_file(file_path)
                files_processed += 1
        
        utils.log(f"Processing complete. Files processed: {files_processed}, Total changes: {total_changes}", severity="INFO")
    else:
        utils.log(f"Error: Path does not exist: {input_path}", severity="ERROR")

if __name__ == "__main__":
    main()
