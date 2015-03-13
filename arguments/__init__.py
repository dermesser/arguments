# coding=utf-8
"""
arguments
Active8 (04-03-15)
license: GNU-GPL2
"""
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from builtins import super
from builtins import dict
from builtins import open
from builtins import int
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import range
from builtins import object

# noinspection PyUnresolvedReferences
from fallbackdocopt import DocoptExit, docopt

import os
import sys
import yaml
from os.path import exists, expanduser
from consoleprinter import console, handle_ex, consoledict, get_print_yaml, colorize_for_print


class SchemaError(Exception):
    """Error during Schema validation."""
    def __init__(self, autos, errors):
        """
        @type autos: str, unicode
        @type errors: str, unicode
        @return: None
        """
        self.autos = autos if isinstance(autos, list) else [autos]
        self.errors = errors if isinstance(errors, list) else [errors]
        Exception.__init__(self, self.code)

    @property
    def code(self):
        """
        code
        """

        def uniq(seq):
            """
            @type seq: str, unicode
            @return: None
            """
            seen = set()
            seen_add = seen.add
            return [x for x in seq if x not in seen and not seen_add(x)]

        a = uniq(i for i in self.autos if i is not None)
        e = uniq(i for i in self.errors if i is not None)

        if e:
            return '\n'.join(e)

        return '\n'.join(a)


class And(object):
    """
    And
    """
    def __init__(self, *args, **kw):
        """
        @type args: tuple
        @type **kw: str, unicode
        @return: None
        """
        self._args = args
        assert list(kw) in (['error'], [])
        self._error = kw.get('error')

    def __repr__(self):
        """
        __repr__
        """
        return '%s(%s)' % (self.__class__.__name__,

                           ', '.join(repr(a) for a in self._args))

    def validate(self, data):
        """
        @type data: str, unicode
        @return: None
        """
        for s in [Schema(s, error=self._error) for s in self._args]:
            data = s.validate(data)

        return data


class Or(And):
    """
    Or
    """
    def validate(self, data):
        """
        @type data: str, unicode
        @return: None
        """
        x = SchemaError([], [])
        for s in [Schema(s, error=self._error) for s in self._args]:
            try:
                return s.validate(data)
            except SchemaError as _x:
                x = _x
        raise SchemaError(['%r did not validate %r' % (self, data)] + x.autos, [self._error] + x.errors)


class Use(object):
    """
    Use
    """
    def __init__(self, callable_, error=None):
        """
        @type callable_: str, unicode
        @type error: str, unicode, None
        @return: None
        """
        assert callable(callable_)
        self._callable = callable_
        self._error = error

    def __repr__(self):
        """
        __repr__
        """
        return '%s(%r)' % (self.__class__.__name__, self._callable)

    def validate(self, data):
        """
        @type data: str, unicode
        @return: None
        """
        try:
            return self._callable(data)
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors)
        except BaseException as x:
            f = self._callable.__name__
            raise SchemaError('%s(%r) raised %r' % (f, data, x), self._error)


COMPARABLE, CALLABLE, VALIDATOR, TYPE, DICT, ITERABLE = list(range(6))


def priority(s):
    """
    @type s: str, unicode
    @return: None
    """
    if type(s) in (list, tuple, set, frozenset):
        return ITERABLE

    if isinstance(s, dict):
        return DICT

    if issubclass(type(s), type):
        return TYPE

    if hasattr(s, 'validate'):
        return VALIDATOR

    if callable(s):
        return CALLABLE
    else:
        return COMPARABLE


class Schema(object):
    """
    Schema
    """
    def __init__(self, schema, error=None):
        """
        @type schema: str, unicode
        @type error: str, unicode, None
        @return: None
        """
        self._schema = schema
        self._error = error

    def __repr__(self):
        """
        __repr__
        """
        return '%s(%r)' % (self.__class__.__name__, self._schema)

    def add_void_schema_item(self, key):
        """
        @type key: str, unicode
        @return: None
        """
        self._schema[key] = Use(str)

    def get_keys(self):
        """
        get_keys
        """
        return list(self._schema.keys())

    def validate(self, data):
        """
        @type data: str, unicode
        @return: None
        """
        s = self._schema
        e = self._error
        nkey = None
        nvalue = None
        flavor = priority(s)

        if flavor == ITERABLE:
            data = Schema(type(s), error=e).validate(data)
            return type(s)(Or(*s, error=e).validate(d) for d in data)

        if flavor == DICT:
            data = Schema(dict, error=e).validate(data)
            new = type(data)()  # new - is a dict of the validated values
            x = None
            coverage = set()  # non-optional schema keys that were matched
            covered_optionals = set()

            # for each key and value find a schema entry matching them, if any
            sorted_skeys = list(sorted(s, key=priority))

            for key, value in list(data.items()):
                valid = False
                skey = None

                for skey in sorted_skeys:
                    svalue = s[skey]
                    try:
                        nkey = Schema(skey, error=e).validate(key)
                    except SchemaError:
                        pass
                    else:
                        try:
                            nvalue = Schema(svalue, error=e).validate(value)
                        except SchemaError as _x:
                            # noinspection PyUnusedLocal
                            x = _x
                            raise
                        else:
                            (covered_optionals if isinstance(skey, Optional)
                             else coverage).add(skey)
                            valid = True
                            break

                if valid:
                    if nkey is None:
                        raise AssertionError("nkey is None")

                    if nvalue is None:
                        raise AssertionError("nvalue is None")

                    new[nkey] = nvalue
                elif skey is not None:
                    if x is not None:
                        raise SchemaError(['invalid value for key %r' % key] + x.autos, [e] + x.errors)

            required = set(k for k in s if not isinstance(k, Optional))
            if coverage != required:
                raise SchemaError('missed keys %r' % (required - coverage), e)

            if len(new) != len(data):
                wrong_keys = set(data.keys()) - set(new.keys())
                s_wrong_keys = ', '.join('%r' % (k,) for k in sorted(wrong_keys))
                raise SchemaError('wrong keys %s in %r' % (s_wrong_keys, data), e)

            # Apply default-having optionals that haven't been used:
            defaults = set(k for k in s if isinstance(k, Optional) and
                           hasattr(k, 'default')) - covered_optionals

            for default in defaults:
                new[default.key] = default.default

            return new

        if flavor == TYPE:
            if isinstance(data, s):
                return data
            else:
                raise SchemaError('%r should be instance of %r' % (data, s), e)

        if flavor == VALIDATOR:
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),

                                  self._error)

        if flavor == CALLABLE:
            f = s.__name__
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%s(%r) raised %r' % (f, data, x),

                                  self._error)

            raise SchemaError('%s(%r) should evaluate to True' % (f, data), e)

        if s == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (s, data), e)


MARKER = object()


class Optional(Schema):
    """Marker for an optional part of Schema."""
    def __init__(self, *args, **kwargs):
        """
        @type args: tuple
        @type kwargs: dict
        @return: None
        """
        default = kwargs.pop('default', MARKER)
        super(Optional, self).__init__(*args, **kwargs)

        if default is not MARKER:
            # See if I can come up with a static key to use for myself:
            if priority(self._schema) != COMPARABLE:
                raise TypeError(

                    'Optional keys with defaults must have simple, '
                    'predictable values, like literal strings or ints. '
                    '"%r" is too complex.' % (self._schema,))

            self.default = default
            self.key = self._schema


def not_exists(path):
    """
    @type path: str, unicode
    @return: None
    """
    return not exists(path)


class Arguments(object):
    """
    Arguments
    """
    def __init__(self, doc=None, validateschema=None, argvalue=None, yamlstr=None, yamlfile=None, parse_arguments=True, persistoption=False, alwaysfullhelp=False, version=None):
        """
        @type doc: str, unicode, None
        @type validateschema: Schema, None
        @type yamlfile: str, unicode, None
        @type yamlstr: str, unicode, None
        @type parse_arguments: bool
        @type argvalue: str, unicode, None
        @return: None
        """
        self.m_once = None
        self.write = None
        self.load = None
        self.m_schema = validateschema
        self.m_reprdict = {}
        self.m_doc = ""
        whitespacecount = 0

        for line in doc.strip().split("\n"):
            line = line.rstrip()

            if whitespacecount == 0:
                whitespacecount = len(line) - len(line.lstrip())

            line = line[whitespacecount:]
            self.m_doc += line + "\n"

        self.m_argv = argvalue
        self.m_persistoption = persistoption
        self.m_alwaysfullhelp = alwaysfullhelp
        self.m_version = version

        if yamlfile:
            self.from_yaml_file(yamlfile)
        elif yamlstr:
            self.from_yaml(yamlstr)
        elif parse_arguments is True:
            parsedok = False
            exdoc = False
            sysex = False
            try:
                self.parse_arguments(self.m_schema)
                parsedok = True
            except DocoptExit:
                exdoc = True
                raise
            except SystemExit:
                sysex = True
                raise

            finally:
                if parsedok is False and exdoc is False and sysex is False:
                    print()

            if self.write is not None:
                fp = open(self.write, "w")
                self.write = ""
                fp.write(self.as_yaml())
                self.write = fp.name
                fp.close()
            elif self.load is not None:
                self.from_yaml_file(self.load)

        if yamlfile:
            raise AssertionError("not implemented")

    def parse_arguments(self, schema=True):
        """
        @type schema: Schema
        @return: None
        """
        arguments = None

        if schema is not None:
            self.m_schema = schema

        if self.load is None:
            if self.m_doc is None:
                # noinspection PyUnresolvedReferences
                import __main__
                self.m_doc = __main__.__doc__

            if self.m_persistoption is True:
                optsplit = self.m_doc.split("Options:")
                optsplit[0] += "Options:\n"
                optsplit[0] += """    -w --write=<writeymlpath>\tWrite arguments yaml file.\n    -l --load=<loadymlpath>\tLoad arguments yaml file."""
                self.m_doc = "".join(optsplit)
                console(optsplit)

            self.m_doc += "\n"
            try:
                if self.m_argv is None:
                    self.m_argv = sys.argv[1:]

                arguments = dict(docopt(self.m_doc, self.m_argv, options_first=True, version=self.m_version))

                if "--help" in [s for s in arguments.values() if isinstance(s, str)] or "-h" in [s for s in arguments.values() if isinstance(s, str)]:
                    print(self.m_doc.strip())
                    exit(1)
            except DocoptExit:
                if self.m_alwaysfullhelp is True:
                    print(self.m_doc.strip())
                    exit(1)
                else:
                    if "-h" in self.m_argv or "--help" in self.m_argv:
                        print(self.m_doc.strip())
                        exit(1)
                    else:
                        raise

            k = ""
            try:
                if isinstance(arguments, dict):
                    for k in arguments:
                        if "folder" in k or "path" in k:
                            if hasattr(arguments[k], "replace"):
                                arguments[k] = arguments[k].replace("~", expanduser("~"))

                                if arguments[k].strip() == ".":
                                    arguments[k] = os.getcwd()

                                if "./" in arguments[k].strip():
                                    arguments[k] = arguments[k].replace("./", os.getcwd() + "/")

                                arguments[k] = arguments[k].rstrip("/").strip()

            except AttributeError as e:
                console("Attribute error:" + k.strip(), "->", str(e), color="red")

                if isinstance(arguments, dict):
                    for k in arguments:
                        console(k.strip(), color="red")

                handle_ex(e)
        else:
            if isinstance(self.load, str):
                # noinspection PyTypeChecker
                loaded_arguments = yaml.load(open(self.load))
                arguments = {}
                for k in loaded_arguments["options"]:
                    arguments["op_" + k] = loaded_arguments["options"][k]
                for k in loaded_arguments["positional"]:
                    arguments["pa_" + k] = loaded_arguments["positional"][k]
            else:
                console("self.load is not a str", self.load, color="red")
        try:
            if not isinstance(arguments, dict):
                raise AssertionError("arguments should be a dict by now")

            if "--" in arguments:
                del arguments["--"]

            validate_arguments = dict((x.replace("<", "").replace(">", "").replace("--", "").replace("-", "_"), y) for x, y in arguments.items())

            if self.m_schema is not None:
                schema_keys = self.m_schema.get_keys()

                for k in list(validate_arguments.keys()):
                    if k not in schema_keys:
                        self.m_schema.add_void_schema_item(k)
                self.m_schema.validate(validate_arguments)

            arguments = dict((x.replace("<", "pa_").replace(">", "").replace("--", "op_").replace("-", "_"), y) for x, y in arguments.items())
        except SchemaError as e:
            console("SchemaError", "".join([x for x in e.errors if x]), color="red", plainprint=True)
            print(self.m_doc.strip())
            exit(1)

        options, positional_arguments = self.sort_arguments(arguments)
        self._set_fields(positional_arguments, options)

    @staticmethod
    def not_exists(path):
        """
        @type path: str, unicode
        @return: None
        """
        return not_exists(path)

    def for_print(self):
        """
        for_print
        """
        return self.as_string()

    def as_string(self):
        """
        as_string
        """
        return get_print_yaml(self.as_yaml())

    def __str__(self):
        """
        __str__
        """
        s = (str(self.__class__).replace(">", "").replace("class ", "").replace("'", "") + " object at 0x%x>" % id(self))
        s += "\n"
        s += consoledict(self.m_reprdict, printval=False)
        return s

    def _set_fields(self, positional, options):
        """
        _parse_arguments
        """
        dictionary = {}

        if positional is not None and options is not None:
            self.positional = positional.copy()
            self.options = options.copy()
            dictionary = positional.copy()
            dictionary.update(options.copy())
            self.m_reprdict = {"positional": positional.copy(),
                               "options": options.copy()}

        for k, v in dictionary.items():
            if hasattr(v, "strip"):
                v = v.strip("'")
                v = v.strip('"')

            setattr(self, str(k), v)

    @staticmethod
    def sort_arguments(arguments):
        """
        @type arguments: dict
        @return: tuple
        """
        opts = {}
        posarg = {}

        for k in arguments:
            try:
                possnum = arguments[k]

                if isinstance(possnum, str):
                    possnum = possnum.replace("'", "").replace('"', '')

                    if "." in possnum:
                        arguments[k] = float(possnum)
                    else:
                        arguments[k] = int(possnum)

            except ValueError:
                pass

            key = k.replace("pa_", "").replace("op_", "").strip()

            if len(key) > 0:
                if k.startswith("pa_"):
                    posarg[k.replace("pa_", "")] = arguments[k]

                if k.startswith("op_"):
                    opts[k.replace("op_", "")] = arguments[k]

        return opts, posarg

    def as_yaml(self):
        """
        as_yaml
        """
        return "---\n" + yaml.dump(self.m_reprdict, default_flow_style=False)

    def from_yaml_file(self, file_path):
        """
        @type file_path: str, unicode
        @return: None
        """
        if exists(file_path):
            self.from_yaml(open(file_path).read())
        else:
            raise AssertionError("File not found: " + file_path)

    def from_yaml(self, yamldata):
        """
        @type yamldata: str, unicode
        @return: None
        """
        self.m_reprdict = yaml.load(yamldata)
