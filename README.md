<div align="center">
  <img src="assets/icon.png" alt="icon" width="32" />
</div>

# keypirinha-bookmark-txt

Search bookmarks in plain text files, inspired by [bookmarks.txt](https://github.com/soulim/bookmarks.txt).

Authors: GLM-5🧙‍♂️, scillidan🤡.

The icon is from [Input Prompts](https://www.kenney.nl/assets/input-prompts) by [Kenney](https://www.kenney.nl)

## Features

- Load contents from multiple directories and subdirectories
- Using space between words helps filtering stuffs
- Ignore custom files and dirs
- Three search modes: keyword, direct, all
- Other features

## Bookmark format

```
## https://github.com/soulim/bookmarks.txt/blob/main/bookmarks.txt
https://github.com
https://keypirinha.com          Keypirinha
https://keypirinha.com/api.html Keypirinha - Extending Keypirinha (API)
...
```

## Usage

### Keyword Mode (default: `keyword_mode = true`)

Type `bkm` → Tab → `<query1> <query2> ...`

### Direct Mode (`keyword_mode = false`)

Type directly: `<query1> <query2> ...`

Items will be shown alongside other catalog items.
