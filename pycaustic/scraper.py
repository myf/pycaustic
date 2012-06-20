# -*- coding: utf-8 -*-

import requests
import uuid
import copy
import os

from .patterns import Regex
from .responses import ( DoneLoad, DoneFind, Wait, MissingTags, Reference,
                         Failed, Result )
from .templates import Substitution
from .errors import InvalidInstruction

class Request(object):

    def __init__(self, instruction, tags, input, force, request_id, uri):
        self._instruction = copy.deepcopy(instruction)
        self._tags = tags
        self._input = input
        self._force = force
        self._id = request_id
        self._uri = uri

    @property
    def instruction(self):
        return self._instruction

    @property
    def tags(self):
        return self._tags

    @property
    def input(self):
        return self._input

    @property
    def force(self):
        return self._force

    @property
    def id(self):
        return self._id

    @property
    def uri(self):
        return self._uri


class Scraper(object):

    def __init__(self, session=requests.Session()):
        # We defensively deepcopy session -- advisable?
        self._session = copy.deepcopy(session)

    def _load_uri(self, string):
        """
        Obtain a remote instruction.
        """
        raise NotImplementedError('Remotely constructed instructions not yet supported')

    def _run_children(self, input, then):
        """
        Run a series of children with new input.
        """
        # similar to scrape, except we don't return a Referenced in case of array
        pass

    def _scrape_find(self, req, instruction, description, then):
        """
        Scrape a find instruction
        """
        if 'find' not in instruction:
            raise InvalidInstruction("Missing regex")

        findSub = Substitution(instruction['find'], req.tags)
        replaceSub = Substitution(instruction.get('replace', '$0'), req.tags)
        nameSub = Substitution(instruction.get('name'), req.tags)
        ignore_case = instruction.get('case_insensitive', False)
        multiline = instruction.get('multiline', False)
        dot_matches_all = instruction.get('dot_matches_all', True)

        # Default to full range
        min_match = instruction.get('min_match', 0)
        max_match = instruction.get('max_match', -1)
        match = instruction.get('match', None)

        # Use single match if it was defined
        min_match = min_match if match is None else match
        max_match = max_match if match is None else match

        missing_tags = Substitution.add_missing(findSub, replaceSub, nameSub)
        if len(missing_tags):
            return MissingTags(req, missing_tags)

        # Default to regex as string
        name = nameSub.result if nameSub.result else findSub.result
        replace = replaceSub.result

        regex = Regex(findSub.result, ignore_case, multiline, dot_matches_all, replace)

        results = []
        for substitution in regex.substitutions(req.input):
            results.append(Result(substitution, self._run_children(substitution, then)))

        if len(results):
            return DoneFind(req, name, description, results)
        else:
            return Failed(req, "No matches")

    def _scrape_load(self, req, instruction, force, description, then):
        """
        Scrape a load instruction

        :returns: DoneLoad, Wait, MissingTags, or Failed
        """
        if 'url' not in instruction:
            raise InvalidInstruction("Missing URL")

        method = instruction.get('method', 'get')
        if method not in ['head', 'get', 'post']:
            raise InvalidInstruction("Illegal HTTP method: %s" % method)
        else:
            requester = getattr(self._session, method)

        urlSub = Substitution(instruction['url'], req.tags)
        nameSub = Substitution(instruction.get('name'), req.tags)
        postsSub = Substitution(instruction.get('posts'), req.tags)
        cookiesSub = Substitution(instruction.get('cookies', {}), req.tags)
        headersSub = Substitution(instruction.get('headers', {}), req.tags)

        # Extract our missing tags, if any
        missing_tags = Substitution.add_missing(urlSub, nameSub, postsSub,
                                                cookiesSub)
        if len(missing_tags):
            return MissingTags(req, missing_tags)

        url = urlSub.result
        name = nameSub.result if nameSub.result else url

        if instruction.get('force') != True:
            return Wait(req, name, description)

        posts = postsSub.result
        cookies = cookiesSub.result
        headers = headersSub.result

        try:
            opts = dict(cookies=cookies, headers=headers)
            if method == 'post' or posts:
                opts['data'] = posts

            resp = requester(urlSub.result, **opts)
            if resp.status_code == 200:
                children = self._run_children(resp.text, then)
                result = Result(resp.text, children)
                return DoneLoad(req, name, description, result)
            else:
                return Failed(req, "Status code %s from %s" % (
                    resp.status_code, url))
        except requests.exception.RequestException as e:
            return Failed(req, str(e))

    def _scrape_dict(self, req, instruction):
        """
        Scrape a dict instruction.

        :returns: Response
        """
        then = instruction.pop('then', [])
        description = instruction.pop('description', None)

        # Extend our instruction dict, overwriting keys
        while 'extends' in instruction:
            extends = instruction.pop('extends')
            if isinstance(extends, basestring):
                instruction.update(self._load_uri(extends))
            elif isinstance(extends, dict):
                instruction.update(extends)
            else:
                raise InvalidInstruction("`extends` must be a dict or str")

        if 'find' in instruction:
            return self._scrape_find(req, instruction, description, then)
        elif 'load' in instruction:
            return self._scrape_load(req, instruction, description, then)
        else:
            raise InvalidInstruction("Could not find `find` or `load` key.")

    def scrape(self, instruction, tags={}, input='', force=False, **kwargs):
        """
        Scrape a request.

        :param: instruction An instruction, either as a string, dict, or list
        :type: str, dict, list
        :param: (optional) tags Tags to use for substitution
        :type: dict
        :param: (optional) input Input for Find
        :type: str
        :param: (optional) force Whether to actually load a load
        :type: bool
        :param: (optional) id ID for request
        :type: str

        :returns: Response
        """

        # Have to track down the instruction.
        while isinstance(instruction, basestring):
            instructionSub = Substitution(instruction, tags)
            if instructionSub.missing_tags:
                return MissingTags(self, instructionSub.missingTags)
            instruction = self._load_uri(instructionSub.result)

        req = Request(instruction, tags, input, force,
                      kwargs.pop('id', str(uuid.uuid4())),
                      kwargs.pop('uri', os.getcwd()))

        # Handle each element of list separately within this context.
        if isinstance(instruction, list):
            resps = []
            for i in instruction:
                clone = Scraper(self._session)
                resps.append(clone.scrape(i, tags, input, False, **kwargs))

            return Reference(req, resps)

        # Dict instructions are ones we can actually handle
        elif isinstance(instruction, dict):
            return self._scrape_dict(req, instruction)

        # Fail.
        else:
            raise InvalidInstruction(instruction)
