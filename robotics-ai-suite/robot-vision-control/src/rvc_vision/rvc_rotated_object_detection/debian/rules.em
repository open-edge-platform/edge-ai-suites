#!/usr/bin/make -f
# -*- makefile -*-
# Sample debian/rules that uses debhelper.
# This file was originally written by Joey Hess and Craig Small.
# As a special exception, when this file is copied by dh-make into a
# dh-make output file, you may use that output file without restriction.
# This special exception was added by Craig Small in version 0.37 of dh-make.

# Uncomment this to turn on verbose mode.
export DH_VERBOSE=1
# TODO: remove the LDFLAGS override.  It's here to avoid esoteric problems
# of this sort:
#  https://code.ros.org/trac/ros/ticket/2977
#  https://code.ros.org/trac/ros/ticket/3842
export LDFLAGS=
export PKG_CONFIG_PATH=@(InstallationPrefix)/lib/pkgconfig
# Explicitly enable -DNDEBUG, see:
# 	https://github.com/ros-infrastructure/bloom/issues/327
export DEB_CXXFLAGS_MAINT_APPEND=-DNDEBUG

# Python package installation variables
export PYBUILD_INSTALL_ARGS=--prefix "@(InstallationPrefix)" \
	--install-lib "\$$base/lib/{interpreter}/site-packages" \
	@[ if pass_install_scripts ] --install-scripts "\$$base/bin" @[end if]

DEB_HOST_GNU_TYPE ?= $(shell dpkg-architecture -qDEB_HOST_GNU_TYPE)

%:
	dh $@@ -v --buildsystem=pybuild --with python3 --builddirectory=.obj-$(DEB_HOST_GNU_TYPE)

override_dh_auto_configure:
	# In case we're installing to a non-standard location, look for a setup.sh
	# in the install tree and source it.  It will set things like
	# CMAKE_PREFIX_PATH, PKG_CONFIG_PATH, and PYTHONPATH.
	if [ -f "@(InstallationPrefix)/setup.sh" ]; then . "@(InstallationPrefix)/setup.sh"; fi && \
	dh_auto_configure

override_dh_auto_build:
	# In case we're installing to a non-standard location, look for a setup.sh
	# in the install tree and source it.  It will set things like
	# CMAKE_PREFIX_PATH, PKG_CONFIG_PATH, and PYTHONPATH.
	if [ -f "@(InstallationPrefix)/setup.sh" ]; then . "@(InstallationPrefix)/setup.sh"; fi && \
	dh_auto_build

override_dh_auto_test:
	# In case we're installing to a non-standard location, look for a setup.sh
	# in the install tree and source it.  It will set things like
	# CMAKE_PREFIX_PATH, PKG_CONFIG_PATH, and PYTHONPATH.
	echo -- Running tests. Even if one of them fails the build is not canceled.
	if [ -f "@(InstallationPrefix)/setup.sh" ]; then . "@(InstallationPrefix)/setup.sh"; fi && \
	dh_auto_test || true

override_dh_shlibdeps:
	# In case we're installing to a non-standard location, look for a setup.sh
	# in the install tree and source it.  It will set things like
	# CMAKE_PREFIX_PATH, PKG_CONFIG_PATH, and PYTHONPATH.
	if [ -f "@(InstallationPrefix)/setup.sh" ]; then . "@(InstallationPrefix)/setup.sh"; fi && \
	dh_shlibdeps -l$(CURDIR)/debian/@(Package)/@(InstallationPrefix)/lib/

override_dh_auto_install:
	# In case we're installing to a non-standard location, look for a setup.sh
	# in the install tree and source it.  It will set things like
	# CMAKE_PREFIX_PATH, PKG_CONFIG_PATH, and PYTHONPATH.
	if [ -f "@(InstallationPrefix)/setup.sh" ]; then . "@(InstallationPrefix)/setup.sh"; fi && \
	dh_auto_install

override_dh_auto_clean:
	# In case we're installing to a non-standard location, look for a setup.sh
	# in the install tree and source it.  It will set things like
	# CMAKE_PREFIX_PATH, PKG_CONFIG_PATH, and PYTHONPATH.
	if [ -f "@(InstallationPrefix)/setup.sh" ]; then . "@(InstallationPrefix)/setup.sh"; fi && \
	dh_auto_clean