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

.PHONY: htmlversion
htmlversion:
	@export ENABLE_IGHF=1 && \
	$(SPHINXBUILD_V) "$(SOURCEDIR)" "$(BUILDDIR_V)" -A enable_ighf=1 -t release -t counter
	git stash
	for tag in $$(git tag | grep -E '^[0-9]'); do \
		git checkout $${tag} -q ; \
		cp -r $(SOURCEDIR)/images/html ./${BUILDDIR_V}/$${tag}/_images/html ; \
	done
	git checkout ${COMMIT} -q
	git stash pop -q || :
	mkdir -p ./${BUILDDIR_V}/latest
	cp -r $(SOURCEDIR)/_static/redirect/* ./${BUILDDIR_V}/latest/
	find ./${BUILDDIR_V}/latest -type f -name "*.html" -print0 | \
		xargs -0 sed -i "s/LATEST_TAG/$$(git tag -l --sort -version:refname | head -n 1)/g"
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR_V)."

.PHONY: htmlinternal
htmlinternal:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR_I)" $(SPHINXOPTS) $(O) -A is_latest=1 -t internal
	cp -r $(SOURCEDIR)/images/html ./${BUILDDIR_I}/_images/html
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR_I)."

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
