# CrateDrop open record data

Aggregate statistics about recorded music releases, built from the **Discogs monthly data dump of 1 November 2026** (CC0),
limited to the **3,662,868 releases that have at least one YouTube video**.

Made by [CrateDrop](https://www.cratedrop.app), the random record digger for producers, DJs and collectors. Every row
links to a page where the same numbers are shown as charts, with a random handful of playable records.

Refreshed automatically every month when Discogs publishes a new dump. Also on
[Hugging Face](https://huggingface.co/datasets/cratedrop/open-record-data) and [Kaggle](https://www.kaggle.com/datasets/cratedrop/music-releases-by-style-country-and-year).

## Files

| File | Rows | One row per |
|---|---|---|
| `styles.csv` | 636 | Discogs style with 100+ releases |
| `countries.csv` | 163 | release country with 100+ releases |
| `years.csv` | 116 | release year with 500+ releases |
| `style_decades.csv` | 1,623 | style and decade with 300+ releases |
| `labels.csv` | 1,763 | record label with 200+ releases (first label on the release) |

## Columns

- `releases`: number of releases in the group (every pressing, reissue and format counts as its own release).
- `peak_year`, `median_year`, `year_min`, `year_max`: by release year.
- `vinyl_share`, `cd_share`: share of releases in that main format.
- `seven_inch_share`, `lp_share`: share with the 7" or LP format description.
- `reissue_share`, `compilation_share`: share marked Reissue/Repress or Compilation.
- `main_release_share`: share that Discogs marks as the main release of its master.
- `top_*`: the top entries with release counts, `;`-separated. Artist and label lists in very large groups are
  counted with light pruning of one-off names, which does not change the top entries in practice.

## How it was made

`parse_releases.py` streams the releases XML and keeps releases with a YouTube video; `aggregate.py` counts them per
group. Both scripts are in this repository. Release data only: no images, no user data, no marketplace data.

## License

Public domain ([CC0 1.0](LICENSE)), like the Discogs data it comes from. A link back is appreciated:
"Source: CrateDrop (cratedrop.app), from the Discogs data dump of 1 November 2026."
