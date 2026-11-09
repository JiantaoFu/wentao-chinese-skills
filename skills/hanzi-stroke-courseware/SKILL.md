# Hanzi Stroke Courseware

## What this skill does

- Build lesson courseware for Wentao Chinese （文韬中文） from a list of characters the teacher plans to teach.

- Produce an interactive single-file HTML page with stroke-order animation, a tracing quiz that checks stroke order, and a character to pinyin matching game.

- Produce a 16:9 PPTX deck with one slide per character, an animated stroke-order GIF on each character slide, tracing grids, a matching game slide and speaker notes for the teacher.

- Reuse the four scripts in `scripts/` for every lesson so a new lesson only needs a new words file, never new code.

## Inputs

- Take a words JSON file as the only required input and follow the shape of `examples/words-sample.json` in this skill.

- Read the optional `title` field as the lesson title and default to 笔顺小课堂 when it is absent.

- Read `words` as an array of objects with three string fields.

  - Give each object a `ch` field with exactly one Chinese character.
  - Give each object a `py` field with the pinyin for that character, with tone marks.
  - Give each object a `mean` field with a short gloss, usually a Chinese word plus an English word.

- Read the optional `game_chars` field as up to six characters chosen from `words` for the matching game and default to the first six words when it is absent.

- Write the pinyin and glosses yourself or copy them from the lesson plan the teacher provided.

- Keep the word count near twelve so the deck and the page stay in one lesson sized chunk.

## Build the courseware

- Create a fresh work directory for the lesson and keep the words file, the downloaded data, the GIFs and the outputs inside it.

- Download the stroke data by running `python3 ~/workspace/custom-skills/hanzi-stroke-courseware/scripts/fetch_data.py --words <words.json> --data-dir <workdir>/data` with `muse.exec`.

- Build the HTML page by running `python3 ~/workspace/custom-skills/hanzi-stroke-courseware/scripts/build_html.py --words <words.json> --data-dir <workdir>/data --out <workdir>/lesson.html` with `muse.exec`.

- Generate the GIFs by running `~/workspace/hanzi-sample-src/.venv/bin/python ~/workspace/custom-skills/hanzi-stroke-courseware/scripts/gen_gifs.py --words <words.json> --data-dir <workdir>/data --out-dir <workdir>/gifs` with `muse.exec`.

- Build the deck by running `~/workspace/hanzi-sample-src/.venv/bin/python ~/workspace/custom-skills/hanzi-stroke-courseware/scripts/build_pptx.py --words <words.json> --data-dir <workdir>/data --gif-dir <workdir>/gifs --out <workdir>/lesson.pptx` with `muse.exec`.

- Run the two GIF and PPTX scripts with any Python that has Pillow and python-pptx installed when the interpreter above is unavailable, and say in the delivery which interpreter you used.

- Deliver the HTML file and the PPTX file together unless the user asked for only one format.

- Adjust the script paths when you work from the GitHub repo copy, where this skill lives under `skills/hanzi-stroke-courseware/` inside the `wentao-chinese-skills` repo.

## Check before delivering

- Count the frames of every GIF with Pillow and require more than one frame per GIF, then report the actual frame counts in the delivery.

- Open the finished PPTX with python-pptx and require the slide count to equal the word count plus four, covering the title slide, the how to use slide, the game slide and the end slide.

- Count the GIF parts inside the PPTX media folder and require one GIF per word.

- Render the PPTX to page images with LibreOffice headless and look at the title slide, the game slide and at least two character slides yourself before delivering.

- Fix any text overflow, misaligned grid or clipped character you spot in the render and rebuild before delivering.

- Search the HTML output for external resource references such as a script src, a link href or a CSS url and require none, because the page must work with no network.

- Count the character data sets embedded in the HTML and require the count to equal the number of distinct characters in the words file.

- Treat the Hanzi Writer project URL inside the bundled library license comment as attribution text, not as an external reference.

## Design rules

- Set the slide and page background to paper #FAF6EF and the main text color to ink #263238.

- Set the accent for pinyin and the stroke currently being written to vermilion red #C8432B.

- Set secondary headings and game accents to teal #1F7A6D and small highlights to gold #E3A72F.

- Set large display characters in KaiTi and body text in Microsoft YaHei in the PPTX, with the same KaiTi first font stack in the HTML template.

- Draw every character inside a 米字格 grid with dashed center lines and dashed diagonals.

- Draw the stroke being written in red, the finished strokes in ink and the strokes still to come as a light ghost.

- Keep every character slide on the same fixed layout with the GIF on the left, the character and pinyin on the right and three tracing grids below.

- Keep at most three content blocks on a slide or page section so the layout stays neat and a child can scan it at a glance.

- Keep margins and spacing identical across slides and never let a long gloss push the pinyin or the stroke count off its line.

## Data and licenses

- Credit Hanzi Writer as the source of the animation library and keep the license header inside the bundled `assets/hanzi-writer.min.js` file, which is MIT licensed.

- Credit Make Me a Hanzi as the source of the stroke shapes, which the Arphic Public License covers, and keep the attribution line that the HTML footer and the PPTX end slide already carry.

- Keep the Arphic Public License text at `references/ARPHICPL.TXT` with anything that redistributes the stroke data, and treat modified stroke data as freely available under the same license with a change notice, while your own templates and code stay separate works that the license does not reach.

- Supply the pinyin and glosses in the words file yourself, because the pipeline never uses the dictionary half of Make Me a Hanzi, which is LGPL 3.0 or later from Unihan and CJKlib data.

- Fetch stroke data per lesson with `scripts/fetch_data.py` instead of copying data files between lessons, so each build uses the pinned hanzi-writer-data 2.0.1 release.

## Alternatives for better results

- Prefer the HTML page when the class can open a browser, because the tracing quiz, the slow motion replay and the matching game only work there.

- Prefer the PPTX when the teacher presents from PowerPoint or needs to print the tracing grids, and warn the teacher that the GIF animation plays in slideshow mode.

- Split the lesson into two decks when the teacher brings more than about sixteen characters, instead of shrinking the layout to fit.

## Websites

- [hanzi-writer-data on jsDelivr](https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1/) for the per character stroke JSON files that `scripts/fetch_data.py` downloads. Verify a new character exists there when a fetch fails before you blame the script.

- [Hanzi Writer](https://chanind.github.io/hanzi-writer) for the library documentation and a live demo of the animation and quiz behavior the HTML page relies on.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
