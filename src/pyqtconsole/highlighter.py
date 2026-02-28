from qtpy.QtGui import (QColor, QTextCharFormat, QFont, QSyntaxHighlighter)

import re
from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Token


def format(color, style=''):
    """Return a QTextCharFormat with the given attributes.
    """
    _color = QColor(color)

    _format = QTextCharFormat()
    _format.setForeground(_color)
    if 'bold' in style:
        _format.setFontWeight(QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)

    return _format


# Syntax styles that can be shared by all languages
STYLES = {
    'keyword': format('blue', 'bold'),
    'operator': format('red'),
    'brace': format('darkGray'),
    'defclass': format('black', 'bold'),
    'string': format('magenta'),
    'string2': format('darkMagenta'),
    'comment': format('darkGreen', 'italic'),
    'self': format('black', 'italic'),
    'numbers': format('brown'),
    'inprompt': format('darkBlue', 'bold'),
    'outprompt': format('darkRed', 'bold'),
    'fstring': format('darkCyan', 'bold'),
    'escape': format('darkorange', 'bold'),
}


class PromptHighlighter(object):

    def __init__(self, formats=None):
        self.styles = styles = dict(STYLES, **(formats or {}))
        self.rules = [
            # Match the prompt incase of a console
            (re.compile(r'IN[^\:]*'), 0, styles['inprompt']),
            (re.compile(r'OUT[^\:]*'), 0, styles['outprompt']),
            # Numeric literals
            (re.compile(r'\b[+-]?[0-9]+\b'), 0, styles['numbers']),
        ]

    def highlight(self, text):
        for expression, nth, format in self.rules:
            for m in expression.finditer(text):
                yield (m.start(nth), m.end(nth) - m.start(nth), format)


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for the Python language using Pygments.
    """

    def __init__(self, document, formats=None):
        QSyntaxHighlighter.__init__(self, document)

        self.styles = dict(STYLES, **(formats or {}))
        self.lexer = PythonLexer()

        # Map Pygments token types to our text formats
        styles = self.styles
        self.token_formats = {
            Token.Keyword: styles['keyword'],
            Token.Keyword.Constant: styles['keyword'],
            Token.Keyword.Declaration: styles['keyword'],
            Token.Keyword.Namespace: styles['keyword'],
            Token.Keyword.Pseudo: styles['keyword'],
            Token.Keyword.Reserved: styles['keyword'],
            Token.Keyword.Type: styles['keyword'],
            Token.Name.Builtin: styles['keyword'],

            Token.Name.Class: styles['defclass'],
            Token.Name.Function: styles['defclass'],
            Token.Name.Decorator: styles['defclass'],

            Token.String: styles['string'],
            Token.String.Double: styles['string'],
            Token.String.Single: styles['string'],
            Token.String.Doc: styles['string2'],
            Token.String.Escape: styles['escape'],
            Token.String.Interpol: styles['fstring'],
            Token.String.Affix: styles['string'],

            Token.Number: styles['numbers'],
            Token.Number.Integer: styles['numbers'],
            Token.Number.Float: styles['numbers'],
            Token.Number.Hex: styles['numbers'],
            Token.Number.Oct: styles['numbers'],
            Token.Number.Bin: styles['numbers'],

            Token.Comment: styles['comment'],
            Token.Comment.Single: styles['comment'],
            Token.Comment.Multiline: styles['comment'],

            Token.Operator: styles['operator'],
            Token.Punctuation: styles['brace'],
        }

        # Cache tokenized document by content hash
        self._cached_doc_text = None
        self._line_formats = {}

    def _to_utf16_offset(self, text, position):
        """Convert Python string position to UTF-16 offset for Qt.

        Qt uses UTF-16 encoding internally, where some characters
        (like emoji) take 2 code units. This converts Python string
        indices to UTF-16 positions.
        """
        return len(text[:position].encode('utf-16-le')) // 2

    def highlightBlock(self, text):
        """Apply syntax highlighting using Pygments."""
        if not text:
            return

        # Get document text
        doc_text = self.document().toPlainText()

        # Retokenize if document changed
        if doc_text != self._cached_doc_text:
            self._cached_doc_text = doc_text
            self._line_formats = self._tokenize_document(doc_text)

        # Apply formatting for current line
        block_num = self.currentBlock().blockNumber()
        if block_num in self._line_formats:
            for start, length, fmt in self._line_formats[block_num]:
                self.setFormat(start, length, fmt)

    def _tokenize_document(self, text):
        """Tokenize entire document, return formatting by line number."""
        line_formats = {}
        if not text:
            return line_formats

        lines = text.split('\n')
        line_starts = [0]
        for line in lines[:-1]:
            line_starts.append(line_starts[-1] + len(line) + 1)

        position = 0
        for token_type, token_value in lex(text, self.lexer):
            if not token_value:
                continue

            fmt = self._get_format_for_token(token_type)
            if not fmt:
                position += len(token_value)
                continue

            # Find which line(s) this token spans
            token_end = position + len(token_value)
            start_line = 0
            for i, ls in enumerate(line_starts):
                if position >= ls:
                    start_line = i
                else:
                    break

            # Handle tokens across multiple lines
            current_line = start_line
            chars_processed = 0

            while (chars_processed < len(token_value) and
                   current_line < len(lines)):
                line_start_pos = line_starts[current_line]
                line_text = lines[current_line]

                # Position within current line
                token_pos_in_line = max(
                    0, position + chars_processed - line_start_pos)

                # How many chars of token on this line
                remaining = len(token_value) - chars_processed
                chars_on_line = min(remaining, len(line_text) - token_pos_in_line)

                if chars_on_line > 0:
                    utf16_start = self._to_utf16_offset(
                        line_text, token_pos_in_line)
                    utf16_end = self._to_utf16_offset(
                        line_text, token_pos_in_line + chars_on_line)

                    if current_line not in line_formats:
                        line_formats[current_line] = []
                    line_formats[current_line].append(
                        (utf16_start, utf16_end - utf16_start, fmt))

                    chars_processed += chars_on_line

                # Skip the newline character
                if chars_processed < len(token_value):
                    chars_processed += 1
                    current_line += 1

            position = token_end

        return line_formats

    def _get_format_for_token(self, token_type):
        """Find the most specific format for a token type."""
        format_to_apply = None
        current_type = token_type
        while current_type and not format_to_apply:
            format_to_apply = self.token_formats.get(current_type)
            if hasattr(current_type, 'parent'):
                current_type = current_type.parent
            else:
                current_type = None
        return format_to_apply
