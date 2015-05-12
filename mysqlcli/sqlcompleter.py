from __future__ import print_function
import logging
from prompt_toolkit.completion import Completer, Completion
from .packages.completion_engine import suggest_type
from .packages.parseutils import last_word
from re import compile


_logger = logging.getLogger(__name__)

class SQLCompleter(Completer):
    keywords = ['ACCESS', 'ADD', 'ALL', 'ALTER TABLE', 'AND', 'ANY', 'AS',
            'ASC', 'AUDIT', 'BETWEEN', 'BY', 'CASE', 'CHAR', 'CHECK',
            'CLUSTER', 'COLUMN', 'COMMENT', 'COMPRESS', 'CONNECT', 'COPY',
            'CREATE', 'CURRENT', 'DATABASE', 'DATE', 'DECIMAL', 'DEFAULT',
            'DELETE FROM', 'DELIMITER', 'DESC', 'DESCRIBE', 'DISTINCT', 'DROP',
            'ELSE', 'ENCODING', 'ESCAPE', 'EXCLUSIVE', 'EXISTS', 'EXTENSION',
            'FILE', 'FLOAT', 'FOR', 'FORMAT', 'FORCE_QUOTE', 'FORCE_NOT_NULL',
            'FREEZE', 'FROM', 'FULL', 'FUNCTION', 'GRANT', 'GROUP BY',
            'HAVING', 'HEADER', 'IDENTIFIED', 'IMMEDIATE', 'IN', 'INCREMENT',
            'INDEX', 'INITIAL', 'INSERT INTO', 'INTEGER', 'INTERSECT', 'INTO',
            'IS', 'JOIN', 'LEFT', 'LEVEL', 'LIKE', 'LIMIT', 'LOCK', 'LONG',
            'MAXEXTENTS', 'MINUS', 'MLSLABEL', 'MODE', 'MODIFY', 'NOAUDIT',
            'NOCOMPRESS', 'NOT', 'NOWAIT', 'NULL', 'NUMBER', 'OIDS', 'OF',
            'OFFLINE', 'ON', 'ONLINE', 'OPTION', 'OR', 'ORDER BY', 'OUTER',
            'OWNER', 'PCTFREE', 'PRIMARY', 'PRIOR', 'PRIVILEGES', 'QUOTE',
            'RAW', 'RENAME', 'RESOURCE', 'REVOKE', 'RIGHT', 'ROW', 'ROWID',
            'ROWNUM', 'ROWS', 'SELECT', 'SESSION', 'SET', 'SHARE', 'SIZE',
            'SMALLINT', 'START', 'SUCCESSFUL', 'SYNONYM', 'SYSDATE', 'TABLE',
            'TEMPLATE', 'THEN', 'TO', 'TRIGGER', 'UID', 'UNION', 'UNIQUE',
            'UPDATE', 'USE', 'USER', 'VALIDATE', 'VALUES', 'VARCHAR',
            'VARCHAR2', 'VIEW', 'WHEN', 'WHENEVER', 'WHERE', 'WITH', ]

    functions = ['AVG', 'COUNT', 'DISTINCT', 'FIRST', 'FORMAT', 'LAST',
            'LCASE', 'LEN', 'MAX', 'MIN', 'MID', 'NOW', 'ROUND', 'SUM', 'TOP',
            'UCASE']

    def __init__(self, smart_completion=True):
        super(self.__class__, self).__init__()
        self.smart_completion = smart_completion
        self.reserved_words = set()
        for x in self.keywords:
            self.reserved_words.update(x.split())
        self.name_pattern = compile("^[_a-z][_a-z0-9\$]*$")

        self.special_commands = []
        self.databases = []
        self.dbmetadata = {'tables': {}, 'views': {}, 'functions': {}}

        self.all_completions = set(self.keywords + self.functions)

    def escape_name(self, name):
        if name and ((not self.name_pattern.match(name))):
            name = '"%s"' % name

        return name

    def unescape_name(self, name):
        """ Unquote a string."""
        if name and name[0] == '"' and name[-1] == '"':
            name = name[1:-1]

        return name

    def escaped_names(self, names):
        return [self.escape_name(name) for name in names]

    def extend_special_commands(self, special_commands):
        # Special commands are not part of all_completions since they can only
        # be at the beginning of a line.
        self.special_commands.extend(special_commands)

    def extend_database_names(self, databases):
        databases = self.escaped_names(databases)
        self.databases.extend(databases)

    def extend_keywords(self, additional_keywords):
        self.keywords.extend(additional_keywords)
        self.all_completions.update(additional_keywords)

    def extend_relations(self, data, kind):
        """ extend metadata for tables or views

        :param data: list of (rel_name,) tuples
        :param kind: either 'tables' or 'views'
        :return:
        """

        data = [self.escaped_names(d) for d in data]

        # dbmetadata['tables']['table_name'] should be a list of
        # column names. Default to an asterisk
        metadata = self.dbmetadata[kind]
        for relname in data:
            metadata[relname[0]] = ['*']
            self.all_completions.update(relname[0])

    def extend_columns(self, column_data, kind):
        """ extend column metadata

        :param column_data: list of (rel_name, column_name) tuples
        :param kind: either 'tables' or 'views'
        :return:
        """
        column_data = [self.escaped_names(d) for d in column_data]
        metadata = self.dbmetadata[kind]
        for relname, column in column_data:
            metadata[relname].append(column)
            self.all_completions.update(column)

    def extend_functions(self, func_data):

        # func_data is an iterator of (schema_name, function_name)

        # dbmetadata['functions']['schema_name']['function_name'] should return
        # function metadata -- right now we're not storing any further metadata
        # so just default to None as a placeholder
        metadata = self.dbmetadata['functions']

        for f in func_data:
            schema, func = self.escaped_names(f)
            metadata[schema][func] = None
            self.all_completions.add(func)

    def reset_completions(self):
        self.databases = []
        self.dbmetadata = {'tables': {}, 'views': {}, 'functions': {}}
        self.all_completions = set(self.keywords + self.functions)

    @staticmethod
    def find_matches(text, collection, start_only=False):
        """Find completion matches for the given text.

        Given the user's input text and a collection of available
        completions, find completions matching the last word of the
        text.

        If `start_only` is True, the text will match an available
        completion only at the beginning. Otherwise, a completion is
        considered a match if the text appears anywhere within it.

        yields prompt_toolkit Completion instances for any matches found
        in the collection of available completions.

        """

        text = last_word(text, include='most_punctuations').lower()

        for item in sorted(collection):
            match_end_limit = len(text) if start_only else None
            match_point = item.lower().find(text, 0, match_end_limit)

            if match_point >= 0:
                yield Completion(item, -len(text))

    def get_completions(self, document, complete_event, smart_completion=None):
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        if smart_completion is None:
            smart_completion = self.smart_completion

        # If smart_completion is off then match any word that starts with
        # 'word_before_cursor'.
        if not smart_completion:
            return self.find_matches(word_before_cursor, self.all_completions,
                                     start_only=True)

        completions = []
        suggestions = suggest_type(document.text, document.text_before_cursor)

        for suggestion in suggestions:

            _logger.debug('Suggestion type: %r', suggestion['type'])

            if suggestion['type'] == 'column':
                tables = suggestion['tables']
                _logger.debug("Completion column scope: %r", tables)
                scoped_cols = self.populate_scoped_cols(tables)
                cols = self.find_matches(word_before_cursor, scoped_cols)
                completions.extend(cols)

            elif suggestion['type'] == 'function':
                funcs = self.dbmetadata['functions'].keys()

                funcs = self.find_matches(word_before_cursor, funcs,
                                          start_only=True)
                completions.extend(funcs)

            elif suggestion['type'] == 'table':
                tables = self.dbmetadata['tables'].keys()
                tables = self.find_matches(word_before_cursor, tables)
                completions.extend(tables)

            elif suggestion['type'] == 'view':
                views = self.dbmetadata['views'].keys()
                views = self.find_matches(word_before_cursor, views)
                completions.extend(views)

            elif suggestion['type'] == 'alias':
                aliases = suggestion['aliases']
                aliases = self.find_matches(word_before_cursor, aliases)
                completions.extend(aliases)

            elif suggestion['type'] == 'database':
                dbs = self.find_matches(word_before_cursor, self.databases)
                completions.extend(dbs)

            elif suggestion['type'] == 'keyword':
                keywords = self.find_matches(word_before_cursor, self.keywords,
                                             start_only=True)
                completions.extend(keywords)

            elif suggestion['type'] == 'special':
                special = self.find_matches(word_before_cursor,
                                            self.special_commands,
                                            start_only=True)
                completions.extend(special)

        return completions

    def populate_scoped_cols(self, scoped_tbls):
        """ Find all columns in a set of scoped_tables
        :param scoped_tbls: list of (table, alias) tuples
        :return: list of column names
        """

        columns = []
        meta = self.dbmetadata

        for tbl in scoped_tbls:
            relname = self.escape_name(tbl[1])

            # We don't know if relname is a table or view. Since
            # tables and views cannot share the same name, we can check one
            # at a time
            try:
                columns.extend(meta['tables'][relname])

                # Table exists, so don't bother checking for a view
                continue
            except KeyError:
                pass

            try:
                columns.extend(meta['views'][relname])
            except KeyError:
                pass

        return columns
