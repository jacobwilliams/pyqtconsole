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

    def _to_utf16_offset(self, text, position):
        """Convert Python string position to UTF-16 offset for Qt.

        Qt uses UTF-16 encoding internally, where some characters
        (like emoji) take 2 code units. This converts Python string
        indices to UTF-16 positions.
        """
        return len(text[:position].encode('utf-16-le')) // 2

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text using Pygments.
        """
        if text:

            # Always retokenize - cache would need to track content changes
            # For a console, this is fine since we only highlight visible lines
            formats = self._tokenize_line(text)

            # Apply formatting for this block's tokens
            for start_pos, length, format_obj in formats:
                self.setFormat(start_pos, length, format_obj)

    def _tokenize_line(self, text):
        """Tokenize a single line and return formatting information."""
        formats = []

        # Add newline if not present - Pygments needs it for proper tokenization
        text_to_lex = text if text.endswith('\n') else text + '\n'

        position = 0
        for token_type, token_value in lex(text_to_lex, self.lexer):
            if not token_value:
                continue

            # Skip the added newline in output
            if position >= len(text):
                break

            format_to_apply = self._get_format_for_token(token_type)
            if format_to_apply:
                utf16_start = self._to_utf16_offset(text, position)
                # Make sure we don't go past the actual text length
                token_len = min(len(token_value), len(text) - position)
                utf16_end = self._to_utf16_offset(text, position + token_len)
                formats.append(
                    (utf16_start, utf16_end - utf16_start, format_to_apply))

            position += len(token_value)

        return formats

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
