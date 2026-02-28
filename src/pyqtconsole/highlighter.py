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

        # Cache for document tokenization
        self._token_cache = {}
        self._cached_text = None

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
        if not text:
            return

        # Get the full document text
        doc_text = self.document().toPlainText()

        # Retokenize if document changed
        if doc_text != self._cached_text:
            self._cached_text = doc_text
            self._token_cache = self._tokenize_document(doc_text)

        # Find which line we're on
        current_block = self.currentBlock()
        block_number = current_block.blockNumber()

        # Apply formatting for this block's tokens
        if block_number in self._token_cache:
            for start_pos, length, format_obj in self._token_cache[block_number]:
                self.setFormat(start_pos, length, format_obj)

    def _tokenize_document(self, text):
        """Tokenize the entire document and organize by line number."""
        tokens_by_line = {}

        if not text:
            return tokens_by_line

        # Split document into lines to know line boundaries
        lines = text.split('\n')
        line_positions = [0]  # Start position of each line
        for line in lines[:-1]:
            line_positions.append(line_positions[-1] + len(line) + 1)

        # Tokenize entire document
        position = 0
        for token_type, token_value in lex(text, self.lexer):
            if not token_value:
                continue

            format_to_apply = self._get_format_for_token(token_type)
            if not format_to_apply:
                position += len(token_value)
                continue

            # Find which line(s) this token is on
            token_start = position
            token_end = position + len(token_value)

            # Binary search for starting line
            line_num = 0
            for i, line_start in enumerate(line_positions):
                if token_start >= line_start:
                    line_num = i
                else:
                    break

            # Handle tokens that may span multiple lines
            remaining = token_value
            while remaining and line_num < len(lines):
                line_start = line_positions[line_num]
                line_text = lines[line_num]

                # Calculate position within this line
                pos_in_line = token_start - line_start
                chars_in_line = min(len(remaining),
                                    len(line_text) - pos_in_line)

                if chars_in_line > 0:
                    utf16_start = self._to_utf16_offset(line_text, pos_in_line)
                    utf16_end = self._to_utf16_offset(line_text,
                                                      pos_in_line + chars_in_line)

                    if line_num not in tokens_by_line:
                        tokens_by_line[line_num] = []
                    tokens_by_line[line_num].append(
                        (utf16_start, utf16_end - utf16_start, format_to_apply))

                # Move to next line
                remaining = remaining[chars_in_line + 1:]  # +1 for newline
                if line_num + 1 < len(line_positions):
                    token_start = line_positions[line_num + 1]
                else:
                    token_start = token_end
                line_num += 1

            position = token_end

        return tokens_by_line

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
