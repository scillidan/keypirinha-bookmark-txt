import keypirinha as kp
import keypirinha_util as kpu
import os
import re
import fnmatch
import ctypes

class BookmarkTxt(kp.Plugin):
    DEFAULT_KEYWORD = "bkmt"
    DEFAULT_COMMENT_PREFIX = "##"
    DEFAULT_MAX_DESC_LEN = "20%"
    DEFAULT_DIRECTORIES = []
    DEFAULT_PATTERNS = ["*.txt"]
    DEFAULT_IGNORE = []

    def __init__(self):
        super().__init__()
        self.bookmarks = []
        self.keyword = self.DEFAULT_KEYWORD
        self.keyword_mode = True
        self.comment_prefix = self.DEFAULT_COMMENT_PREFIX
        self.max_desc_len = self.DEFAULT_MAX_DESC_LEN
        self._max_desc_len_raw = str(self.DEFAULT_MAX_DESC_LEN)
        self.directories = self.DEFAULT_DIRECTORIES
        self.patterns = self.DEFAULT_PATTERNS
        self.ignore = self.DEFAULT_IGNORE
        self.browser_args = ""

    def on_start(self):
        self._read_config()
        self._load_bookmarks()
        self.on_catalog()
        icon_handle = self.load_icon("res://BookmarkTxt/assets/icon.ico")
        self.set_default_icon(icon_handle)

    def on_stop(self):
        pass

    def on_reload(self):
        self._read_config()
        self._load_bookmarks()
        self.on_catalog()

    def _read_config(self):
        settings = self.load_settings()

        self.keyword = settings.get_stripped(
            "keyword", "main", self.DEFAULT_KEYWORD).lower()

        self.keyword_mode = settings.get_bool("keyword_mode", "main", True)

        self.comment_prefix = settings.get_stripped(
            "comment_prefix", "main", self.DEFAULT_COMMENT_PREFIX)

        self.max_desc_len = settings.get_int(
            "max_desc_len", "main", self.DEFAULT_MAX_DESC_LEN)

        self._max_desc_len_raw = settings.get_stripped(
            "max_desc_len", "main", str(self.DEFAULT_MAX_DESC_LEN))

        directories_raw = settings.get("directories", "main", "")
        if isinstance(directories_raw, str):
            self.directories = [
                x.strip().rstrip(";") 
                for x in directories_raw.replace("\n", ";").split(";") 
                if x.strip()
            ]

        patterns_raw = settings.get_stripped("patterns", "main", "")
        if isinstance(patterns_raw, str):
            self.patterns = [
                x.strip() 
                for x in patterns_raw.replace(";", ",").split(",") 
                if x.strip()
            ] or self.DEFAULT_PATTERNS

        ignore_raw = settings.get("ignore", "main", "")
        if isinstance(ignore_raw, str):
            self.ignore = [
                x.strip() 
                for x in ignore_raw.replace("\n", ";").split(";") 
                if x.strip()
            ]

        self.browser_args = settings.get_stripped("browser_args", "main", "")

    def _should_ignore_path(self, filepath):
        if not self.ignore:
            return False

        filepath_norm = os.path.normpath(filepath).lower()
        filepath_forward = filepath_norm.replace("\\", "/")
        filename = os.path.basename(filepath_forward)

        for pattern in self.ignore:
            pattern = pattern.strip()
            if not pattern:
                continue

            pattern_lower = pattern.lower()

            if pattern_lower.endswith("/"):
                dir_name = pattern_lower.rstrip("/")
                parts = filepath_forward.split("/")
                for part in parts:
                    if part == dir_name:
                        return True
            else:
                if fnmatch.fnmatch(filename, pattern_lower):
                    return True

        return False

    def _matches_pattern(self, filename):
        if not self.patterns:
            return True
        filename_lower = filename.lower()
        for pattern in self.patterns:
            if fnmatch.fnmatch(filename_lower, pattern.lower()):
                return True
        return False

    def _load_bookmarks(self):
        self.bookmarks = []

        for dir_path in self.directories:
            expanded_dir = os.path.expandvars(os.path.expanduser(dir_path))

            if not os.path.isdir(expanded_dir):
                continue

            for root, dirs, files in os.walk(expanded_dir):
                for f in files:
                    if not self._matches_pattern(f):
                        continue

                    filepath = os.path.join(root, f)

                    if self._should_ignore_path(filepath):
                        continue

                    self._parse_bookmark_file(filepath)

    def _parse_bookmark_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(self.comment_prefix):
                        continue

                    url, title = self._parse_line(line)
                    if url:
                        self.bookmarks.append({
                            'url': url,
                            'title': title if title else self._strip_protocol(url),
                            'file': filepath
                        })
        except Exception as e:
            self.err(f"Error reading bookmark file {filepath}: {e}")

    def _parse_line(self, line):
        url_pattern = r'^(https?://[^\s]+)'
        match = re.match(url_pattern, line)

        if match:
            url = match.group(1)
            title = line[match.end():].strip()
            return url, title

        return None, None

    def _strip_protocol(self, url):
        return re.sub(r'^https?://', '', url)

    def _get_effective_max_desc_len(self):
        raw = self._max_desc_len_raw.strip()
        if raw.endswith('%'):
            try:
                percent = float(raw[:-1].strip())
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                char_width_approx = 8
                return int(screen_width * percent / 100 / char_width_approx)
            except:
                return self.DEFAULT_MAX_DESC_LEN
        else:
            return self.max_desc_len

    def _truncate_title(self, title):
        max_len = self._get_effective_max_desc_len()
        if len(title) <= max_len:
            return title
        return title[:max_len - 3] + "..."

    def _matches_search(self, title, url, search_terms):
        if not search_terms:
            return True

        searchable = (title + " " + url).lower()
        return all(term.lower() in searchable for term in search_terms)

    def on_catalog(self):
        if self.keyword_mode:
            catalog = []
            catalog.append(self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label=self.keyword,
                short_desc="Search bookmarks",
                target=self.keyword,
                args_hint=kp.ItemArgsHint.ACCEPTED,
                hit_hint=kp.ItemHitHint.IGNORE
            ))
        else:
            catalog = []
            for bm in self.bookmarks:
                display_title = self._truncate_title(bm['title'])
                display_url = self._strip_protocol(bm['url'])
                catalog.append(self.create_item(
                    category=kp.ItemCategory.URL,
                    label=display_title,
                    short_desc=display_url,
                    target=bm['url'],
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.KEEPALL
                ))
        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        if not self.keyword_mode:
            return

        if not items_chain or items_chain[0].category() != kp.ItemCategory.KEYWORD:
            return

        search_text = user_input.strip()

        search_terms = search_text.split() if search_text else []

        suggestions = []
        for bm in self.bookmarks:
            if self._matches_search(bm['title'], bm['url'], search_terms):
                display_title = self._truncate_title(bm['title'])
                display_url = self._strip_protocol(bm['url'])

                suggestions.append(self.create_item(
                    category=kp.ItemCategory.URL,
                    label=display_title,
                    short_desc=display_url,
                    target=bm['url'],
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.KEEPALL
                ))

        if suggestions:
            self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.LABEL_ASC)
        else:
            self.set_suggestions([self.create_error_item(
                label="No bookmarks found",
                short_desc=f"Search: {search_text}" if search_text else "Type to search bookmarks"
            )])

    def on_execute(self, item, action):
        if item.category() == kp.ItemCategory.URL:
            url = item.target()
            self.dbg(f"Opening URL: {url}, browser: {self.browser_args}")
            if self.browser_args:
                kpu.shell_execute(self.browser_args, [url])
            else:
                kpu.web_open_url(url)
