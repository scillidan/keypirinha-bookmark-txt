PACKAGE_NAME = BookmarkTxt
VERSION = 0.0.2
DIST_DIR = dist
FILES = bookmark_txt.py bookmarktxt.ini README.md LICENSE

.PHONY: all clean dist

all: dist

dist:
	@mkdir -p $(DIST_DIR)
	7z a -tzip "$(DIST_DIR)/$(PACKAGE_NAME).keypirinha-package" $(FILES)

clean:
	@rm -rf $(DIST_DIR)

info:
	@echo "Package: $(PACKAGE_NAME)"
	@echo "Version: $(VERSION)"
	@echo "Files: $(FILES)"
