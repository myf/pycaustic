#!/usr/bin/env python
# -*- coding: utf-8 -*-

from helpers import unittest
from pycaustic.templates import Substitution
from pycaustic.errors import TemplateError, TemplateResultError


class TestSubstitution(unittest.TestCase):

    def test_string_replace(self):
        """
        Test a simple string replace.
        """
        sub = Substitution('roses are {{color}}', dict(color='red'))

        self.assertEquals([], sub.missing_tags)
        self.assertEquals('roses are red', sub.result)

    def test_float_replace(self):
        """
        Floats should be coerced to strings.
        """
        sub = Substitution(4.5, {})

        self.assertEqual('4.5', sub.result)

    def test_int_replace(self):
        """
        Ints should be coerced to strings.
        """
        sub = Substitution(-100, {})

        self.assertEqual('-100', sub.result)

    def test_several_replacements(self):
        """
        Test replacing several strings.
        """
        sub = Substitution('roses are {{roses}}, violets are {{violets}}',
                           dict(roses='red', violets='blue'))

        self.assertEquals([], sub.missing_tags)
        self.assertEquals('roses are red, violets are blue', sub.result)

    def test_missing_tag(self):
        """
        Missing tags should be populated
        """
        sub = Substitution('roses are {{color}}', {})
        self.assertEquals(['color'], sub.missing_tags)

    def test_missing_tag_access_raises_error(self):
        """
        We should raise an exception when we try to get the result of an
        incomplete template.
        """
        sub = Substitution('roses are {{color}}', {})

        with self.assertRaises(TemplateResultError):
            sub.result

    def test_invalid_template_class(self):
        """
        We should not be able to create templates from anything but strings,
        dicts, and None.
        """
        bad_template = ['foo', 'bar'], 100

        with self.assertRaises(TemplateError):
            Substitution(bad_template, {})

    def test_dict_substitution(self):
        """
        We should be able to sub both keys and values from a dict.
        """
        tmpl = {
            '{{flower1}}': '{{color1}}',
            '{{flower2}}': '{{color2}}'
        }
        sub = Substitution(tmpl, {
            'flower1': 'roses',
            'flower2': 'violets',
            'color1': 'red',
            'color2': 'blue'
        })

        self.assertEquals([], sub.missing_tags)
        self.assertEquals({
            'roses': 'red',
            'violets':'blue'
        }, sub.result)

    def test_dict_substitution_missing(self):
        """
        We should get a complete list of everything missing in keys/values
        """
        tmpl = {
            '{{flower1}}': '{{color1}}',
            '{{flower2}}': '{{color2}}'
        }
        sub = Substitution(tmpl, {
            'flower2': 'violets',
            'color1': 'red',
        })

        self.assertEquals(['flower1', 'color2'], sub.missing_tags)

    def test_url_encoding(self):
        """
        By default, we should be encoding stuff in {{}}
        """
        tmpl = "{{foo}}"
        sub = Substitution(tmpl, {
            'foo': "bar baz"
        })
        self.assertEquals("bar+baz", sub.result)

    def test_not_url_encoding(self):
        """
        Triple brackets mean that it's not encoded inside.
        """
        tmpl = "{{{foo}}}"
        sub = Substitution(tmpl, {
            'foo': "bar baz"
        })
        self.assertEquals("bar baz", sub.result)

    def test_not_url_encoding_a_url(self):
        """
        We really want to make sure we don't touch these in {{{}}}!
        """
        tmpl = "{{{url}}}"
        url = "http://www.host.com/foo/bar/baz%20is%20ok?foo=bar&baz=boo"
        sub = Substitution(tmpl, {
            'url': url
        })
        self.assertEquals(url, sub.result)

    def test_substituting_blank(self):
        """
        We should be able to substitute in a blank string
        """
        tmpl = "nothing inside '{{blank}}'"
        sub = Substitution(tmpl, {
            'blank': ''
        })
        self.assertEquals("nothing inside ''", sub.result)
