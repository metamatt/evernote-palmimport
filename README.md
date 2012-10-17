# Palm Desktop memo importer for Evernote

## Overview

This is the source repository for evernote-palmimporter, a utility app I wrote to migrate
note data from [Palm Desktop](http://kb.hpwebos.com/wps/portal/kb/common/article/33529_en.html)
(or any Palm OS device that syncs with Palm Desktop) into [Evernote](http://www.evernote.com).

For users wanting the immediately usable artifacts instead of source code, the distribution
point is [http://www.maddogsw.com/evernote-utilities/evernote-palm-importer/](http://www.maddogsw.com/evernote-utilities/evernote-palm-importer/).

## (Very sketchy) build instructions

The makefiles and support infrastructure here may be in rough shape if you don't follow a
crossplatform development methodology similar to what I'm currently using, which is:

* code, test, and build mostly on a recent version of Mac OS X
* occasionally test and build under Windows
* invoke the packaging scripts on Mac OS X to build the non-Windows distributions,
  then on Windows to build the Windows distribution, then again on Mac OS X to
  wrap everything up for actual distribution.

