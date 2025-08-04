# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS          = "-W"
SPHINXBUILD         = sphinx-build
SPHINXBUILD_V       = sphinx-multiversion
SOURCEDIR           = source
BUILDDIR            = build
BUILDDIR_I          = build/html_internal
BUILDDIR_V          = build/html_version
COMMIT              = $(shell git rev-parse HEAD)

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

clean:
	rm -rf "$(BUILDDIR)"

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O) -t release

.PHONY: html
html:
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O) -A is_latest=1 -t release
	cp -r $(SOURCEDIR)/images/html ./${BUILDDIR}/html/_images/html

.PHONY: ditaxml
ditaxml:
	rm -rf ./${BUILDDIR}/doctrees
	rm -rf ./${BUILDDIR}/ditaxml
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O) -A is_latest=1 -t ditaxml
	cp -r $(SOURCEDIR)/images/html ./${BUILDDIR}/ditaxml/_images/html

.PHONY: doxygen
doxygen:
	rm -rf source/doxygen/rvc_control/xml source/doxygen/rvc_vision/xml
	cp -rp ../src/rvc_control/xml source/doxygen/rvc_control/
	cp -rp ../src/rvc_vision/xml source/doxygen/rvc_vision/
