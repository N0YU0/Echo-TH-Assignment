BASELINE_IMAGE ?= nginx:1.25-bookworm
PATCHED_IMAGE  ?= nginx:1.25-bookworm-patched
DEB_OUT_DIR    ?= build/out
PYTHON         ?= python3

.PHONY: all help deb image test scan clean

all: deb image test

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  all    Build .deb package, container image, and run compatibility tests (default)"
	@echo "  deb    Compile patched nginx .deb package from upstream source into $(DEB_OUT_DIR)/"
	@echo "  image  Build drop-in replacement image ($(PATCHED_IMAGE)) from Containerfile"
	@echo "  test   Run side-by-side compatibility test suite against $(BASELINE_IMAGE)"
	@echo "  scan   Run Trivy and Grype vulnerability scans (baseline, patched, and VEX)"
	@echo "  clean  Remove built .deb artifacts and any leftover test containers"
	@echo "  help   Show this help message"

deb:
	mkdir -p $(DEB_OUT_DIR)
	DOCKER_BUILDKIT=1 docker build -f build/Dockerfile --target builder -t echo-nginx-deb-builder .
	docker rm -f echo-deb-extract 2>/dev/null || true
	docker create --name echo-deb-extract echo-nginx-deb-builder
	docker cp echo-deb-extract:/out/. $(DEB_OUT_DIR)/
	docker rm -f echo-deb-extract

image: deb
	DOCKER_BUILDKIT=1 docker build -f Containerfile -t $(PATCHED_IMAGE) .

test:
	BASELINE_IMAGE=$(BASELINE_IMAGE) PATCHED_IMAGE=$(PATCHED_IMAGE) $(PYTHON) test/compat_test.py

scan:
	BASELINE_IMAGE=$(BASELINE_IMAGE) PATCHED_IMAGE=$(PATCHED_IMAGE) $(PYTHON) test/run_scans.py

clean:
	rm -rf $(DEB_OUT_DIR)/*.deb
	docker rm -f echo-compat-base echo-compat-patch echo-compat-base-custom echo-compat-patch-custom 2>/dev/null || true
