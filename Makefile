# 1. help (default target — must come first)
help:
	@echo "================================================"
	@echo "       $(OWNER)/$(PROJECT_NAME) by Startr.Cloud"
	@echo "================================================"
	@echo "This is the default make command."
	@echo "This command lists available make commands."
	@echo ""
	@echo "Usage example:"
	@echo "    make verify"
	@echo ""
	@echo "Available make commands:"
	@echo ""
	@LC_ALL=C $(MAKE) -pRrq -f $(firstword $(MAKEFILE_LIST)) : 2>/dev/null | \
		awk -v RS= -F: '/(^|\n)# Files(\n|$$)/,/(^|\n)# Finished Make data base/ { \
		if ($$1 !~ "^[#.]") {print $$1}}' | \
		sort | \
		grep -E -v -e '^[^[:alnum:]]' -e '^$@$$'
	@echo ""

# 2. Dynamic variables (git-derived)
PROJECTPATH := $(shell git rev-parse --show-toplevel)
PROJECT     := $(shell echo $$(basename $(PROJECTPATH)) | tr '[:upper:]' '[:lower:]')
# Use symbolic-ref (clean failure on empty repos) → short SHA (detached HEAD) → develop fallback.
# Do NOT use `git rev-parse --abbrev-ref HEAD` — it prints "HEAD" to stdout AND fails on a
# no-commits repo, producing a corrupted "HEAD develop" value.
FULL_BRANCH := $(shell git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null || echo "develop")
BRANCH      := $(shell echo $(FULL_BRANCH) | sed 's/.*\///' | tr '[:upper:]' '[:lower:]')
TAG         := $(shell git describe --always --tag 2>/dev/null || echo "v0.0.0")

# Owner and project name extracted from git remote URL
REMOTE_URL   := $(shell git config --get remote.origin.url 2>/dev/null || echo "unknown/unknown")
OWNER        := $(shell echo $(REMOTE_URL) | sed -E 's|.*[:/]([^/]+)/[^/]+(.git)?$$|\1|')
PROJECT_NAME := $(shell echo $(REMOTE_URL) | sed -E 's|.*[:/][^/]+/([^/]+)(.git)?$$|\1|' | sed 's/\.git$$//')

CONTAINER := $(PROJECT)-$(BRANCH)

# The package's own claim about its version. setup.py reads the same string.
PKG_VERSION := $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' django_startr/__init__.py)

# Load environment overrides from .env if present
-include .env

# 3. show_vars + verify (debug / one-shot self-check)
show_vars:
	@echo "=== Dynamic Variables ==="
	@echo "PROJECTPATH=$(PROJECTPATH)"
	@echo "PROJECT=$(PROJECT)"
	@echo "OWNER=$(OWNER)"
	@echo "PROJECT_NAME=$(PROJECT_NAME)"
	@echo "FULL_BRANCH=$(FULL_BRANCH)"
	@echo "BRANCH=$(BRANCH)"
	@echo "TAG=$(TAG)"
	@echo "PKG_VERSION=$(PKG_VERSION)"
	@echo "CONTAINER=$(CONTAINER)"
	@echo "REMOTE_URL=$(REMOTE_URL)"
	@echo ""

# The tag and the package must agree. A release that ships a version the package
# does not claim is the drift this check exists to refuse.
version_check:
	@if [ -z "$(PKG_VERSION)" ]; then \
		echo "FAIL: django_startr/__init__.py has no __version__"; exit 1; fi
	@newest=$$(git tag --sort=-v:refname | head -n 1 | sed 's/^v//'); \
	if [ -z "$$newest" ]; then \
		echo "WARN: no git tag yet. Seed one with: git tag v$(PKG_VERSION)"; \
	elif [ "$$newest" != "$(PKG_VERSION)" ]; then \
		echo "DRIFT: newest tag v$$newest != __version__ $(PKG_VERSION)"; exit 1; \
	else \
		echo "ok  version   v$$newest matches __version__"; \
	fi

# One-shot scaffold self-check. Bundles every read-only verification into a
# single make invocation so post-scaffold testing isn't N separate processes.
verify: show_vars require_gitflow_next version_check pkg_check
	@echo "=== Targets defined in this Makefile ==="
	@LC_ALL=C $(MAKE) -pRrq -f $(firstword $(MAKEFILE_LIST)) : 2>/dev/null | \
		awk -v RS= -F: '/(^|\n)# Files(\n|$$)/,/(^|\n)# Finished Make data base/ { \
		if ($$1 !~ "^[#.]") {print "  " $$1}}' | \
		sort -u | \
		grep -E -v -e '^  [^[:alnum:]]'
	@echo ""
	@echo "OK: Makefile scaffold verified."

# 4. Git-flow-next release/hotfix flow
require_gitflow_next:
	@if ! git flow version 2>/dev/null | grep -q 'git-flow-next'; then \
		echo "Error: git-flow-next required (Go rewrite). Install: brew install git-flow-next"; \
		exit 1; \
	fi

minor_release: require_gitflow_next
	# Start a minor release with incremented minor version
	git flow release start $$(git tag --sort=-v:refname | sed 's/^v//' | head -n 1 | awk -F'.' '{print $$1"."$$2+1".0"}') && echo "or use 'make release_finish' to finish the release"

patch_release: require_gitflow_next
	# Start a patch release with incremented patch version
	git flow release start $$(git tag --sort=-v:refname | sed 's/^v//' | head -n 1 | awk -F'.' '{print $$1"."$$2"."$$3+1}') && echo "or use 'make release_finish' to finish the release"

major_release: require_gitflow_next
	# Start a major release with incremented major version
	git flow release start $$(git tag --sort=-v:refname | sed 's/^v//' | head -n 1 | awk -F'.' '{print $$1+1".0.0"}') && echo "or use 'make release_finish' to finish the release"

hotfix: require_gitflow_next
	# Start a hotfix with incremented n.n.n.n version (incrementing the fourth number)
	git flow hotfix start $$(git tag --sort=-v:refname | sed 's/^v//' | head -n 1 | awk -F'.' '{print $$1"."$$2"."$$3"."$$4+1}') && echo "or use 'make hotfix_finish' to finish the hotfix"

release_finish: require_gitflow_next
	git flow release finish && git push origin develop && git push origin master && git push --tags && git checkout develop

hotfix_finish: require_gitflow_next
	git flow hotfix finish && git push origin develop && git push origin master && git push --tags && git checkout master

# 5. Project targets
#
# This package has no app of its own to run. It is a generator, so the useful
# targets are the ones that prove it still generates and that what it generates
# is what the contract says.

# Local development runs under pipenv. Containers get their own build; these
# targets are for the fully-local loop, and PY is the one place that knows how
# to reach the virtualenv.
PY := pipenv run python
PIPENV := pipenv

# Build or refresh the local dev environment. Django is a real dependency of
# the test suite, so without this three runtime tests skip and the migration's
# most important guarantees go unchecked.
dev_install:
	$(PIPENV) install --dev --python 3.11
	@$(MAKE) --no-print-directory env_check

# Refuses the silent-skip failure mode: a green suite that never ran the tests
# that matter reads exactly like a green suite that did.
env_check:
	@$(PY) -c "import django, jinja2; print('ok  env       django %s, jinja2 %s' % (django.get_version(), jinja2.__version__))" 2>/dev/null \
		|| { echo "FAIL: no local dev env. Run: make dev_install"; exit 1; }

# Package sanity: every subpackage setup.py must ship is importable, and the
# init files exist. The old .gitignore hid every __init__.py, which is exactly
# the failure this refuses to let back in.
pkg_check:
	@fail=0; \
	for d in django_startr django_startr/admin_skin django_startr/management django_startr/management/commands django_startr/templatetags; do \
	  if [ ! -f "$$d/__init__.py" ]; then echo "MISSING: $$d/__init__.py"; fail=1; \
	  else echo "ok  init      $$d/__init__.py"; fi; \
	done; \
	found=$$($(PY) -c "from setuptools import find_packages; print(len(find_packages(include=['django_startr','django_startr.*'])))" 2>/dev/null); \
	if [ "$$found" != "5" ]; then echo "FAIL: find_packages sees $$found packages, expected 5"; fail=1; \
	else echo "ok  packages  find_packages sees 5"; fi; \
	exit $$fail

# The migration gate. Once the stubs are Jinja2 there must be no DTL escaping
# machinery left anywhere in them — that machinery IS the thing being removed,
# so its absence is the only honest completion test.
stub_check:
	@if grep -rn "templatetag\|verbatim" django_startr/templates/django_startr/ >/dev/null 2>&1; then \
		echo "FAIL: DTL escaping machinery still present in the stubs:"; \
		grep -rn "templatetag\|verbatim" django_startr/templates/django_startr/; \
		exit 1; \
	else echo "ok  stubs     no templatetag/verbatim machinery"; fi

# Generated markup must never carry hyperscript. AI-UI's ui_dispatch.py refuses
# all three attribute forms whatever the admin grant says, so a stub that
# reintroduces one silently breaks every Sprig built from this generator.
csp_check:
	@if grep -rEn '(^|[[:space:]])(_|script|data-script)[[:space:]]*=' django_startr/templates/django_startr/*.html >/dev/null 2>&1; then \
		echo "FAIL: interpreted script attribute in a stub:"; \
		grep -rEn '(^|[[:space:]])(_|script|data-script)[[:space:]]*=' django_startr/templates/django_startr/*.html; \
		exit 1; \
	else echo "ok  csp       no interpreted script attributes"; fi

# Full suite. env_check first, so a missing dev environment fails loudly
# instead of quietly skipping the runtime tests.
# A skip is a failure here. The Django-dependent gates run only where this
# package owns the settings, so a suite that reports "OK (skipped=2)" has
# quietly stopped checking the nav and the column picker. Bare "OK" or nothing.
test: env_check
	$(PY) -m compileall -q django_startr
	@out=$$($(PY) -m unittest django_startr.tests 2>&1); echo "$$out"; \
	  echo "$$out" | grep -qx "OK" || { echo "FAIL: suite not clean (a skip counts)"; exit 1; }
	@$(MAKE) --no-print-directory pkg_check stub_check csp_check

# 6. things_clean
#
# Nothing here holds user data — every gitignored path is build output or a
# scratch directory the generator writes during manual testing.
things_clean:
	git clean --exclude='!.env*' -Xdf

# 7. .PHONY declarations
.PHONY: help show_vars verify version_check require_gitflow_next \
	minor_release patch_release major_release hotfix \
	release_finish hotfix_finish things_clean \
	pkg_check stub_check csp_check dev_install env_check test
