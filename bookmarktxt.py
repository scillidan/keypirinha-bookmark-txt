import keypirinha as kp
import keypirinha_util as kpu
import os
import re
import fnmatch
import ctypes
import shlex
import subprocess

class BookmarkTxt(kp.Plugin):
    DEFAULT_KEYWORD = "bkm"
    DEFAULT_COMMENT_PREFIX = "#"
    DEFAULT_MAX_DESC_LEN = "20%"
    DEFAULT_INCLUDE = ["*.txt", "*.bkm"]
    ITEM_CAT_BOOKMARK = kp.ItemCategory.USER_BASE + 1
    ITEM_CAT_FORMAT = kp.ItemCategory.USER_BASE + 2

    def __init__(self):
        super().__init__()
        self._bookmarks = []
        self._keyword = self.DEFAULT_KEYWORD
        self._comment_prefix = self.DEFAULT_COMMENT_PREFIX
        self._max_desc_len = 0
        self._max_desc_len_raw = str(self.DEFAULT_MAX_DESC_LEN)
        self._files = []
        self._directories = []
        self._include = list(self.DEFAULT_INCLUDE)
        self._exclude = []
        self._default_cmd = ""
        self._scheme_cmds = {}
        self._format_order = "alpha_asc"
        self._format_include = []
        self._format_exclude = []
        self._notify = True
        self._omit_scheme = True
        self._loaded_files = {}
        self._icon_handle = None

    def on_start(self):
        self._read_config()
        self._load_bookmarks()
        self._icon_handle = self.load_icon("res://BookmarkTxt/assets/icon.ico")
        self.set_default_icon(self._icon_handle)
        self._set_catalog()

    def on_stop(self):
        pass

    def on_reload(self):
        self._read_config()
        self._load_bookmarks()
        if not self._icon_handle:
            self._icon_handle = self.load_icon("res://BookmarkTxt/assets/icon.ico")
            self.set_default_icon(self._icon_handle)
        self._set_catalog()

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()
            self._format_all_files()
            self._load_bookmarks()
            self._set_catalog()

    def on_catalog(self):
        self._set_catalog()

    def _set_catalog(self):
        self.set_catalog([self.create_item(
            category=self.ITEM_CAT_FORMAT,
            label="Format Bookmarks",
            short_desc="Sort bookmarks",
            target="format",
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.KEEPALL,
            icon_handle=self._icon_handle
        )])

    def _semicolons(self, raw):
        if not isinstance(raw, str):
            return []
        return [x.strip() for x in raw.replace("\n", ";").split(";") if x.strip()]

    def _read_config(self):
        settings = self.load_settings()

        self._keyword = settings.get_stripped(
            "keyword", "main", self.DEFAULT_KEYWORD).lower()

        self._comment_prefix = settings.get_stripped(
            "comment_prefix", "main", self.DEFAULT_COMMENT_PREFIX)

        self._max_desc_len = settings.get_int("max_desc_len", "main", 0)
        self._max_desc_len_raw = settings.get_stripped(
            "max_desc_len", "main", str(self.DEFAULT_MAX_DESC_LEN))

        files_raw = settings.get("files", "main", "")
        self._files = [
            os.path.expandvars(os.path.expanduser(x.strip().rstrip(";")))
            for x in self._semicolons(files_raw)
        ]

        self._directories = [
            os.path.expandvars(os.path.expanduser(x.strip().rstrip(";")))
            for x in self._semicolons(settings.get("directories", "main", ""))
        ]

        self._include = self._semicolons(settings.get("include", "main", "")) or list(self.DEFAULT_INCLUDE)
        self._exclude = self._semicolons(settings.get("exclude", "main", ""))

        self._default_cmd = settings.get_stripped("default_cmd", "main", "")

        self._scheme_cmds = {}
        for section in settings.sections():
            if section.lower().startswith("scheme/"):
                scheme = section[7:].lower()
                cmd = settings.get_stripped("cmd", section, "")
                if cmd:
                    self._scheme_cmds[scheme] = cmd

        self._format_order = settings.get_stripped("format_order", "format", "alpha_asc").lower()
        self._format_include = self._semicolons(settings.get("format_include", "format", ""))
        self._format_exclude = self._semicolons(settings.get("format_exclude", "format", ""))
        self._notify = settings.get_bool("notify", "main", True)
        self._omit_scheme = settings.get_bool("omit_scheme", "main", True)

    def _fnmatch_exclude(self, filepath, patterns):
        if not patterns:
            return False
        fp_fwd = os.path.normpath(filepath).lower().replace("\\", "/")
        fname = os.path.basename(fp_fwd)
        for pat in patterns:
            pl = pat.strip().lower()
            if not pl:
                continue
            if pl.endswith("/"):
                dn = pl.rstrip("/")
                for part in fp_fwd.split("/"):
                    if part == dn:
                        return True
            else:
                if fnmatch.fnmatch(fname, pl):
                    return True
        return False

    def _is_excluded(self, filepath):
        return self._fnmatch_exclude(filepath, self._exclude)

    def _is_included(self, filename):
        if not self._include:
            return True
        fl = filename.lower()
        return any(fnmatch.fnmatch(fl, p.lower()) for p in self._include)

    def _is_format_excluded(self, filepath):
        return self._fnmatch_exclude(filepath, self._format_exclude)

    def _is_format_included(self, filepath):
        if not self._format_include:
            return True
        fl = os.path.basename(filepath).lower()
        return any(fnmatch.fnmatch(fl, p.lower()) for p in self._format_include)

    def _load_bookmarks(self):
        self._bookmarks = []
        self._loaded_files = {}
        seen = set()

        for fpath in self._files:
            norm = os.path.normpath(fpath).lower()
            if norm in seen:
                continue
            seen.add(norm)
            if os.path.isfile(fpath):
                try:
                    self._loaded_files[fpath] = os.path.getmtime(fpath)
                except OSError:
                    pass
                self._parse_file(fpath)

        for dir_path in self._directories:
            if not os.path.isdir(dir_path):
                continue
            for root, dirs, files in os.walk(dir_path):
                for f in files:
                    if not self._is_included(f):
                        continue
                    filepath = os.path.join(root, f)
                    if self._is_excluded(filepath):
                        continue
                    norm = os.path.normpath(filepath).lower()
                    if norm in seen:
                        continue
                    seen.add(norm)
                    try:
                        self._loaded_files[filepath] = os.path.getmtime(filepath)
                    except OSError:
                        pass
                    self._parse_file(filepath)

    def _parse_line(self, line):
        m = re.search(r'(\w+://\S+)', line)
        if not m:
            return None
        url = m.group(1)
        before = line[:m.start()].strip()
        after = line[m.end():]
        tags = []
        title_after = after.strip()
        sep = after.rfind(' - ')
        if sep >= 0:
            after_tag = after[sep + 3:].strip()
            if after_tag and re.match(r'^[^,\s]+(,[^,\s]+)*$', after_tag):
                title_after = after[:sep].strip()
                tags = [t.strip() for t in after_tag.split(',') if t.strip()]
        parts = [p for p in (before, title_after) if p]
        title = ' '.join(parts).replace('\\-', '-')
        if not title:
            title = re.sub(r'^\w+://', '', url)
        return {'url': url, 'text': title, 'tags': tags, 'raw': line}

    def _parse_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith(self._comment_prefix):
                        continue
                    parsed = self._parse_line(line)
                    if parsed:
                        self._bookmarks.append(parsed)
        except Exception as e:
            self.err(f"Failed to read {filepath}: {e}")

    def _extract_sort_key(self, line):
        parsed = self._parse_line(line)
        if not parsed:
            return ('', '', '')
        return (
            ','.join(parsed['tags']).lower(),
            parsed['text'].lower(),
            parsed['url'].lower()
        )

    def _show_notification(self, title, message):
        if not self._notify:
            return
        try:
            t = title.replace("'", "''")
            m = message.replace("'", "''")
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                f"$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                "$n.Visible=$true;"
                f"$n.ShowBalloonTip(3000,'{t}','{m}','Info');"
                "Start-Sleep 4;$n.Dispose()"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-WindowStyle", "Hidden", "-Command", ps],
                creationflags=0x08000000)
        except Exception:
            self.info(f"[{title}] {message}")

    def _format_all_files(self):
        formatted = []
        for filepath in list(self._loaded_files.keys()):
            if not self._is_format_included(filepath) or self._is_format_excluded(filepath):
                continue
            result = self._format_bookmark_file(filepath)
            if result == "formatted":
                formatted.append(filepath)
            elif result == "error":
                self._show_notification("BookmarkTxt", f"Format error: {os.path.basename(filepath)}")
        if formatted:
            names = ", ".join(os.path.basename(f) for f in formatted)
            self._show_notification("BookmarkTxt", f"Formatted: {names}")

    def _format_bookmark_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                raw = fh.read()
        except Exception as e:
            self.err(f"Failed to read {filepath} for formatting: {e}")
            return "error"

        lines = raw.splitlines()

        comments = []
        url_entries = []
        other_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(self._comment_prefix):
                comments.append(stripped)
                continue
            m = re.search(r'(\w+://\S+)', stripped)
            if m:
                url = m.group(1)
                before = stripped[:m.start()].strip()
                rest = stripped[m.end():]
                formatted_line = url + ('  ' + before if before else '') + rest
                key = self._extract_sort_key(formatted_line)
                url_entries.append((key, formatted_line))
            else:
                other_lines.append(stripped)

        if not url_entries and not other_lines:
            return "skipped"

        reverse = self._format_order.endswith('_desc')
        url_entries.sort(key=lambda x: x[0], reverse=reverse)
        comments.sort(reverse=reverse)

        sorted_lines = [l for l in (comments + [e[1] for e in url_entries] + other_lines) if l.strip()]
        new_content = '\n'.join(sorted_lines) + '\n'

        if new_content == raw:
            return "skipped"

        backup = filepath + ".bak"
        try:
            with open(backup, 'w', encoding='utf-8') as fh:
                fh.write(raw)
        except Exception:
            pass

        try:
            with open(filepath, 'w', encoding='utf-8') as fh:
                fh.write(new_content)
        except Exception as e:
            self.err(f"Failed to write {filepath}: {e}")
            try:
                with open(backup, 'r', encoding='utf-8') as bf:
                    original = bf.read()
                with open(filepath, 'w', encoding='utf-8') as fh:
                    fh.write(original)
                self.err(f"Restored {filepath} from backup")
            except Exception:
                self.err(f"CRITICAL: Failed to restore {filepath}!")
            return "error"

        return "formatted"

    def _calc_max_desc_len(self):
        raw = self._max_desc_len_raw.strip()
        if raw.endswith('%'):
            try:
                pct = float(raw[:-1].strip())
                sw = ctypes.windll.user32.GetSystemMetrics(0)
                return max(20, int(sw * pct / 100 / 8))
            except Exception:
                return 50
        elif self._max_desc_len > 0:
            return self._max_desc_len
        return 50

    def _truncate(self, text):
        ml = self._calc_max_desc_len()
        if len(text) <= ml:
            return text
        return text[:ml - 3] + "..."

    def _make_item(self, bm):
        if self._omit_scheme:
            desc = re.sub(r'^https?://', '', bm['url'])
        else:
            desc = bm['url']
        if bm['tags']:
            desc += ' (' + ', '.join(bm['tags']) + ')'
        return self.create_item(
            category=self.ITEM_CAT_BOOKMARK,
            label=bm['text'],
            short_desc=desc,
            target=bm['url'],
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.KEEPALL,
            icon_handle=self._icon_handle
        )

    def _get_open_cmd(self, url):
        scheme_end = url.find('://')
        if scheme_end > 0:
            scheme = url[:scheme_end].lower()
            if scheme in self._scheme_cmds:
                return self._scheme_cmds[scheme], True
        if self._default_cmd:
            return self._default_cmd, True
        return None, False

    def on_suggest(self, user_input, items_chain):
        text = user_input.strip()
        if not text.lower().startswith(self._keyword):
            return

        args = text[len(self._keyword):].strip()
        if not args:
            items = [self._make_item(bm) for bm in self._bookmarks]
            if items:
                self.set_suggestions(items, kp.Match.ANY, kp.Sort.LABEL_ASC)
            return

        words = [w.lower() for w in args.split() if w]
        suggestions = []
        for bm in self._bookmarks:
            searchable = ' '.join([bm['raw'], ' '.join(bm['tags'])]).lower()
            if all(w in searchable for w in words):
                suggestions.append(self._make_item(bm))

        if suggestions:
            self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.LABEL_ASC)
        else:
            self.set_suggestions([self.create_error_item(
                label="No bookmarks found",
                short_desc=f"Search: {args}"
            )])

    def _execute_with_cmd(self, cmd_str, url):
        expanded = os.path.expandvars(os.path.expanduser(cmd_str))
        try:
            parts = shlex.split(expanded, posix=False)
        except ValueError:
            parts = expanded.split()
        if not parts:
            return
        prog = os.path.expandvars(os.path.expanduser(parts[0].strip('"')))
        args = [a.strip('"') for a in parts[1:]] + [url]
        kpu.shell_execute(prog, args)

    def on_execute(self, item, action):
        if item.category() == self.ITEM_CAT_FORMAT:
            self._format_all_files()
            return
        if item.category() != self.ITEM_CAT_BOOKMARK:
            return
        url = item.target()
        cmd, use_cmd = self._get_open_cmd(url)
        if use_cmd:
            self._execute_with_cmd(cmd, url)
        elif url.startswith('file://'):
            path = url[7:]
            if path.startswith('/') and len(path) > 2 and path[2] == ':':
                path = path[1:]
            path = os.path.normpath(path)
            kpu.shell_execute(path)
        else:
            kpu.web_open_url(url)
