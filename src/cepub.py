#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import os
import json
import shutil
import logging
import optparse
import subprocess
from datetime import datetime
from tempfile import mkdtemp
from os.path import join as pjoin, splitext

__author__ = 'Manuel Huber'
__copyright__ = "Copyright (c) 2014 Manuel Huber."
__version__ = '0.9b'
__docformat__ = "restructuredtext en"

_DEFAULT_LOG_FORMAT = "%(name)s : %(threadName)s : %(levelname)s \
: %(message)s"

_REQUIRED_ELEMENTS = ("title", "bookdir", "filename", "outname",
                      "authors")
_UNOCONV = 'unoconv'

_EBOOK_CONVERT = 'ebook-convert'
_EBOOK_META = 'ebook-meta'

_EBOOK_OPTIONS = ('title', 'authors', 'cover', 'language', 'comments')


class EpubCreatorException(Exception):
    pass


class RequiredFieldMissingError(EpubCreatorException):
    pass


class XHTMLConversionError(EpubCreatorException):
    pass


class EpubConversionError(EpubCreatorException):
    pass


class EpubCreator (object):

    def __init__ (self, settings_file, options=None):
        self._settings_file = settings_file
        self._uno_p = None
        self._tmpdir = None
        self._set = None
        try:
            self._interactive = options.interactive
        except (AttributeError, KeyError):
            logging.warn("Disable interactive mode (option doesn't exist)")
            self._interactive = False

    def _conversion_test (self):
        self._start_uno()
        logging.debug("Creating test file 'test.html'")
        with open(pjoin(self._tmpdir, "test.html"), "w") as f:
            f.write("<html><head><title>Test</title></head><body><h1>Test 1</h1></body>")
        logging.debug("Trying to convert test.html to test.rtf")
        test_p = subprocess.Popen([_UNOCONV, '-f', 'rtf','test.html'],
                                  cwd=self._tmpdir)
        test_p.communicate()
        if test_p.returncode != 0:
            logging.debug("Test conversion failed -> killing soffice.bin...")
            self._kill_soffice()
        else:
            logging.debug("Test succeeded")
        self._stop_uno()

    def _kill_soffice (self):
        ps = ["ps", "-C", "soffice.bin"]
        ret = subprocess.call(ps)
        if (ret == 0) and self._interactive:
            while True:
                subprocess.call(ps)
                ret = raw_input("Kill soffice.bin processes (yes/no)? ")
                if ret == 'yes':
                    logging.info("Killing soffice.bin processes")
                    subprocess.call(['pkill', 'soffice.bin'])
                    break
                else:
                    logging.info("Leave soffice.bin running")
                    break

    def start_conversion (self):
        self._load_settings()
        self._create_tmpdir()
        self._conversion_test()
        self._start_uno()
        self._prepare_conversion()
        self._create_xhtml()
        self._stop_uno()
        self._xhtml_to_epub()

    def _load_settings (self):
        if self._set is not None:
             logging.warn("Overriding old settings")
        with open(self._settings_file, "r") as f:
            self._set = json.load(f)
        missing = (i for i in _REQUIRED_ELEMENTS if i not in self._set)
        missing = tuple(missing)
        if len(missing) != 0:
            logging.error("Missing required fields: %s" % ", ".join(missing))
            raise RequiredFieldMissingError()
        logging.debug("Found all required fields...")
        bname, ext = splitext(self._set['filename'])
        self._set['doc_extension'] = ext
        self._set['basename'] = bname

    def _start_uno (self, warn=True):
        self._stop_uno(warn=warn)
        logging.debug("Starting UNO server")
        self._uno_p = subprocess.Popen([_UNOCONV, "--listener"])
        if self._uno_p.poll() is None:
            logging.debug("UNO server is running");

    def _create_tmpdir (self):
        self._remove_tmpdir(warn=True)
        self._tmpdir = mkdtemp(prefix="cepub_")

    def _prepare_conversion (self):
        self._set['docfilename'] = "%s%s" % (self._set['outname'],
                                             self._set['doc_extension'])
        shutil.copy(pjoin(self._set['bookdir'], self._set['filename']),
                    pjoin(self._tmpdir, self._set['docfilename']))
        self._set['pub_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            path = self._set['cover']
            if not os.path.isfile(path):
                logging.debug("Cover path invalid '%s'; relative to bookdir?" %
                              path)
                path = pjoin(self._set['bookdir'], path)
                if os.path.isfile(path):
                    logging.debug("Cover path is relative; New path: '%s'" %
                                  path)
                    self._set['cover'] = path
                else:
                    logging.warn("Cover path '%s' is invalid -> remove key" %
                                 self._set['cover'])
                    del self._set['cover']
        except KeyError:
            pass
        try:
            with open(self._set['comment_file'], 'r') as f:
                text = f.read()
                if len(text) > 0:
                    logging.debug("Replace comment by comment file '%s'" %
                                  self._set['comment_file'])
                    self._set['comments'] = text
        except KeyError:
            pass
        use_bookdir = False
        try:
            if not os.path.isdir(self._set['outdir']):
                use_bookdir = True
                logging.warn("Ouput directory doesn't exist; use 'bookdir'")
        except KeyError:
            logging.warn("Output directory isn't set; use 'bookdir'")
            use_bookdir = True
        if use_bookdir:
            self._set['outdir'] = self._set['bookdir']

    def _create_xhtml (self):
        logging.debug("Start converting %s to HTML..." %
                      self._set['basename'])
        html_p = subprocess.Popen([_UNOCONV, '-f', 'html',
                                   self._set['docfilename']],
                                  cwd=self._tmpdir)
        html_p.communicate()
        if html_p.returncode != 0:
            raise XHTMLConversionError()
        srcname = "%s.%s" % (self._set['outname'], 'html')
        dstname = "%s.%s" % (self._set['outname'], 'xhtml')
        logging.debug("Rename %s to %s for further processing..." %
                      (srcname, dstname))
        os.rename(pjoin(self._tmpdir, srcname),
                  pjoin(self._tmpdir, dstname))

    def _xhtml_to_epub (self):
        epub_name = "%s.epub" % self._set['outname']
        xhtml_name = "%s.xhtml" % self._set['outname']
        logging.debug("Converting XHTML to EPUB file '%s'" % epub_name)
        args = [_EBOOK_CONVERT, xhtml_name, epub_name,
                '--output-profile=kindle', '--pretty-print',
                '--pubdate=%s' % self._set['pub_date']]
        for i in _EBOOK_OPTIONS:
            if i in self._set:
                args.append("--%s=%s" % (i, self._set[i]))
        logging.debug("Conversion command line: '%s'" % " ".join(args))
        conv_p = subprocess.Popen(args, cwd=self._tmpdir)
        conv_p.communicate()
        if conv_p.returncode != 0:
            logging.error("Conversion to epub failed!")
            raise EpubConversionError()
        logging.info("Conversion to EPUB was succeeful!")
        args = [_EBOOK_META, epub_name, '--date=%s' % self._set['pub_date']]
        meta_p = subprocess.Popen(args, cwd=self._tmpdir)
        meta_p.communicate()
        if meta_p.returncode != 0:
            logging.warn("Couldn't date meta information (date); errno=%d" %
                         meta_p.returncode)
        else:
            logging.info("Adding meta information was successful")
        outfile = pjoin(self._set['outdir'], epub_name)
        logging.info("Copy EPUB file to output directory '%s'" %
                     outfile)
        shutil.copy(pjoin(self._tmpdir, epub_name), outfile)

    def _stop_uno (self, warn=False):
        if self._uno_p is not None:
            if self._uno_p.poll() is None:
                if warn:
                    logging.warn("Uno process is running -> will be terminated")
                logging.debug("Uno process will be terminated")
                self._uno_p.terminate()
            else:
                logging.debug("Uno process has been stopped (ret=%d)" %
                              self._uno_p.returncode)
            self._uno_p = None
        else:
            logging.debug("Uno process not started yet")

    def _remove_tmpdir (self, warn=False):
        if self._tmpdir is not None:
            if warn:
                logging.warn("Remove previous temp-directory '%s'" %
                             self._tmpdir)
            shutil.rmtree(self._tmpdir)
            self._tmpdir = None

    def cleanup (self):
        self._stop_uno()
        self._remove_tmpdir()


def create_epub_main (settings_file, options):
    creator = EpubCreator(settings_file, options)
    try:
        creator.start_conversion()
        logging.info("Conversion finished without error!")
    except Exception as e:
        logging.error("Exception: %s" % str(e))
        raise
    finally:
        logging.debug("Clean up temporary directory")
        creator.cleanup()


def main (argv):
    "Main entry point of this application."

    parser = optparse.OptionParser(
        usage="usage: %prog [options] <settings_file>",
        version=("%prog " + __version__)
    )
    parser.add_option("--verbose", action="store_const", const=logging.DEBUG,
        dest="verb_level", help="Verbose output (DEBUG)"
    )
    parser.add_option("--quiet",
                      action="store_const",
                      const=logging.ERROR,
                      dest="verb_level",
                      help="Non verbose output: only output errors"
    )
    parser.add_option("--non-interactive", action="store_false",
                      dest="interactive", default=True,
                      help="Don't use interactive mode"
    )
    parser.set_defaults(version=False, verb_level=logging.INFO)

    options, args = parser.parse_args(argv)

    logging.basicConfig(stream=sys.stderr, format=_DEFAULT_LOG_FORMAT,
                        level=options.verb_level)
    logging.debug("Starting up '%s' (%s)" % (
        os.path.basename(sys.argv[0]),
        datetime.now().isoformat())
    )

    if len(args) != 1:
        parser.error("Missing positional argument <settings_file>!")
    else:
        create_epub_main(args[0], options)


if __name__ == '__main__':
    main(sys.argv[1:])
