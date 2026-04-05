from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pdf_book_digitizer.diffs import build_unified_diff, write_diff
from pdf_book_digitizer.image_inputs import collect_image_paths, infer_page_number_from_image_path


SUPPORTED_MARKDOWN_SUFFIXES = {".md", ".markdown"}
CHAPTER_ENDS_FILENAME = "chapter-end-pages.json"
END_OF_PAGE_PARAGRAPH_FILENAME = "end-of-page-is-end-of-paragraph.json"
HARD_PAGE_BREAK_FILENAME = "hard-page-break.json"

EDITOR_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OCR Inspection Editor</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f1e8;
      --panel: #fffaf1;
      --ink: #1f1d19;
      --muted: #6f6a61;
      --line: #d8cdbb;
      --accent: #a44d2f;
      --accent-strong: #7f3820;
      --success: #2d6a4f;
      --shadow: 0 18px 48px rgba(55, 37, 17, 0.12);
      --font-ui: "IBM Plex Sans", "Avenir Next", "Segoe UI", sans-serif;
      --font-text: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: var(--font-ui);
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(164, 77, 47, 0.16), transparent 30%),
        radial-gradient(circle at right, rgba(119, 111, 82, 0.16), transparent 28%),
        linear-gradient(180deg, #f7f3eb 0%, var(--bg) 100%);
    }

    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 1fr 220px;
      gap: 12px;
      padding: 16px 12px 16px 16px;
    }

    .panel {
      background: color-mix(in srgb, var(--panel) 92%, white 8%);
      border: 1px solid rgba(111, 106, 97, 0.18);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }

    .main {
      min-width: 0;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 12px;
    }

    .rail {
      display: flex;
      flex-direction: column;
      min-height: 0;
    }

    .sidebar {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      justify-content: flex-start;
      gap: 14px;
      border-radius: 20px;
      background: linear-gradient(180deg, #2f2620, #58402f);
      color: #f7efe3;
      padding: 16px 14px;
      box-shadow: var(--shadow);
    }

    .sidebar-title {
      margin: 0;
      text-align: right;
      font-size: 0.9rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      line-height: 1.3;
    }

    .rail-controls {
      display: flex;
      flex-direction: column;
      gap: 10px;
      align-items: stretch;
    }

    .hint, .status-message {
      margin: 0;
      color: var(--muted);
    }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: flex-start;
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }

    button {
      border: 0;
      border-radius: 999px;
      padding: 11px 16px;
      font: inherit;
      font-weight: 600;
      background: #eadfce;
      color: var(--ink);
      cursor: pointer;
      transition: transform 120ms ease, background 120ms ease;
    }

    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.45; cursor: default; transform: none; }

    .primary { background: var(--accent); color: #fff9f5; }
    .primary:hover { background: var(--accent-strong); }
    .success { background: var(--success); color: #f5fff8; }

    .tooltip-button {
      position: relative;
    }

    .tooltip-button::after {
      content: attr(data-shortcut);
      position: absolute;
      right: calc(100% + 10px);
      top: 50%;
      transform: translateY(-50%) translateX(6px);
      padding: 7px 10px;
      border-radius: 10px;
      background: rgba(31, 29, 25, 0.96);
      color: #fffaf1;
      font-size: 0.78rem;
      line-height: 1;
      white-space: nowrap;
      opacity: 0;
      pointer-events: none;
      transition: opacity 120ms ease, transform 120ms ease;
      box-shadow: 0 10px 24px rgba(31, 29, 25, 0.2);
    }

    .tooltip-button:hover::after,
    .tooltip-button:focus-visible::after {
      opacity: 1;
      transform: translateY(-50%) translateX(0);
    }

    .statusbar {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      align-items: center;
      justify-content: space-between;
      padding: 2px 4px 0;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(320px, 50vw) minmax(420px, 1fr);
      gap: 16px;
      min-height: 0;
    }

    .panel {
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
    }

    .image-panel {
      resize: horizontal;
      overflow: auto;
      min-width: 320px;
      max-width: calc(100vw - 220px);
    }

    .panel-header {
      padding: 12px 16px 8px;
      border-bottom: 1px solid rgba(111, 106, 97, 0.14);
    }

    .panel-header h2 {
      margin: 0 0 4px;
      font-size: 1rem;
    }

    .image-header-row {
      display: flex;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 4px;
    }

    .image-title {
      display: flex;
      flex-direction: column;
      gap: 3px;
      min-width: 0;
    }

    .page-label {
      font-size: 1rem;
      font-weight: 700;
      color: var(--ink);
    }

    .signal-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }

    .signal-pill {
      padding: 7px 12px;
      border-radius: 999px;
      font-size: 0.84rem;
      font-weight: 700;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      border: 1px solid transparent;
    }

    .signal-pill[data-active="false"] {
      background: rgba(216, 205, 187, 0.42);
      border-color: rgba(111, 106, 97, 0.16);
      color: var(--muted);
    }

    .signal-pill.inspected[data-active="true"] {
      background: #d96d2f;
      color: #fff9f5;
      border-color: #ba5422;
    }

    .signal-pill.saved[data-active="true"] {
      background: var(--success);
      color: #f5fff8;
      border-color: #22563f;
    }

    .image-wrap {
      flex: 1;
      min-height: 0;
      overflow: auto;
      padding: 16px;
      display: grid;
      place-items: start center;
      background:
        linear-gradient(135deg, rgba(216, 205, 187, 0.28), rgba(255, 250, 241, 0.55));
    }

    img {
      width: auto;
      max-width: 100%;
      height: min(calc(100vh - 220px), 100%);
      border-radius: 10px;
      box-shadow: 0 12px 32px rgba(55, 37, 17, 0.18);
      background: white;
    }

    .jump-group {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(216, 205, 187, 0.48);
    }

    .jump-group label {
      font-size: 0.95rem;
      color: #fffaf1;
    }

    .jump-group input {
      width: 86px;
      padding: 8px 10px;
      border-radius: 999px;
      border: 1px solid rgba(111, 106, 97, 0.24);
      background: rgba(255, 255, 255, 0.84);
      font: inherit;
      color: var(--ink);
    }

    .paragraph-toggle {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(216, 205, 187, 0.38);
      color: var(--ink);
      cursor: pointer;
      user-select: none;
    }

    .paragraph-toggle input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }

    .toggle-track {
      position: relative;
      width: 44px;
      height: 24px;
      border-radius: 999px;
      background: rgba(111, 106, 97, 0.35);
      transition: background 120ms ease;
      flex: 0 0 auto;
    }

    .toggle-track::after {
      content: "";
      position: absolute;
      top: 3px;
      left: 3px;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #fffaf1;
      box-shadow: 0 2px 6px rgba(31, 29, 25, 0.2);
      transition: transform 120ms ease;
    }

    .paragraph-toggle input:checked + .toggle-track {
      background: #d96d2f;
    }

    .paragraph-toggle input:checked + .toggle-track::after {
      transform: translateX(20px);
    }

    .toggle-label {
      font-size: 0.88rem;
      font-weight: 600;
      line-height: 1.3;
    }

    .paragraph-toggle input:disabled + .toggle-track,
    .paragraph-toggle input:disabled ~ .toggle-label {
      opacity: 0.55;
      cursor: default;
    }

    textarea {
      flex: 1;
      width: 100%;
      resize: none;
      border: 0;
      outline: none;
      padding: 18px;
      background: transparent;
      color: var(--ink);
      font: 1.02rem/1.55 var(--font-text);
    }

    .hint {
      font-size: 0.92rem;
    }

    .status-message[data-level="success"] { color: var(--success); }
    .status-message[data-level="error"] { color: #a12626; }

    @media (max-width: 980px) {
      .shell {
        grid-template-columns: 1fr;
        padding-right: 16px;
      }
      .main {
        grid-template-rows: auto auto 1fr;
      }
      .rail-controls {
        width: 100%;
      }
      .sidebar {
        min-height: 36px;
      }
      .tooltip-button::after {
        right: auto;
        left: 50%;
        top: calc(100% + 8px);
        transform: translateX(-50%) translateY(-6px);
      }
      .tooltip-button:hover::after,
      .tooltip-button:focus-visible::after {
        transform: translateX(-50%) translateY(0);
      }
      .workspace { grid-template-columns: 1fr; }
      .shell { padding: 14px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="main">
      <div class="statusbar">
        <p class="status-message" id="statusMessage" data-level=""></p>
      </div>
      <div class="workspace">
        <section class="panel image-panel">
          <div class="panel-header">
            <div class="image-header-row">
              <div class="image-title">
                <span class="page-label" id="pageLabel">Loading…</span>
                <p class="hint" id="imagePathLabel"></p>
              </div>
              <div class="signal-row">
                <label class="paragraph-toggle tooltip-button" data-shortcut="Cmd/Ctrl+Shift+P">
                  <input id="paragraphToggleInput" type="checkbox" />
                  <span class="toggle-track" aria-hidden="true"></span>
                  <span class="toggle-label">End of page is end of paragraph</span>
                </label>
                <label class="paragraph-toggle tooltip-button" data-shortcut="Cmd/Ctrl+Shift+L">
                  <input id="hardPageBreakToggleInput" type="checkbox" />
                  <span class="toggle-track" aria-hidden="true"></span>
                  <span class="toggle-label">Hard page break</span>
                </label>
                <span class="signal-pill inspected" id="inspectedSignal" data-active="false">Not inspected</span>
                <span class="signal-pill saved" id="savedSignal" data-active="false">Unsaved</span>
              </div>
            </div>
          </div>
          <div class="image-wrap">
            <img id="pageImage" alt="Book page image">
          </div>
        </section>

        <section class="panel">
          <div class="panel-header">
            <h2>Markdown</h2>
          </div>
          <textarea id="editor" spellcheck="false"></textarea>
        </section>
      </div>
    </div>
    <div class="rail">
      <aside class="sidebar">
        <h1 class="sidebar-title">OCR Results Inspector</h1>
        <div class="rail-controls">
          <button id="previousButton" class="tooltip-button" data-shortcut="Cmd/Ctrl+Shift+PageUp">Previous Page</button>
          <button id="skipNextButton" class="tooltip-button" data-shortcut="Cmd/Ctrl+Shift+PageDown">Next Page Without Saving</button>
          <button id="saveButton" class="primary tooltip-button" data-shortcut="Cmd/Ctrl+S">Save</button>
          <button id="nextButton" class="success tooltip-button" data-shortcut="Cmd/Ctrl+Shift+Enter">Save &amp; Next</button>
          <button id="chapterButton">Mark end of chapter</button>
          <div class="jump-group">
            <label for="jumpInput">Jump to</label>
            <input id="jumpInput" type="text" inputmode="numeric" pattern="[0-9]*" />
            <button id="jumpButton">Go</button>
          </div>
          <button id="nextUninspectedButton">Go to next uninspected page</button>
        </div>
      </aside>
    </div>
  </div>

  <script>
    const state = {
      index: 0,
      total: 0,
      isDirty: false,
      page: null,
    };

    const editor = document.getElementById("editor");
    const pageImage = document.getElementById("pageImage");
    const pageLabel = document.getElementById("pageLabel");
    const imagePathLabel = document.getElementById("imagePathLabel");
    const statusMessage = document.getElementById("statusMessage");
    const inspectedSignal = document.getElementById("inspectedSignal");
    const savedSignal = document.getElementById("savedSignal");
    const paragraphToggleInput = document.getElementById("paragraphToggleInput");
    const hardPageBreakToggleInput = document.getElementById("hardPageBreakToggleInput");
    const previousButton = document.getElementById("previousButton");
    const skipNextButton = document.getElementById("skipNextButton");
    const saveButton = document.getElementById("saveButton");
    const nextButton = document.getElementById("nextButton");
    const chapterButton = document.getElementById("chapterButton");
    const jumpInput = document.getElementById("jumpInput");
    const jumpButton = document.getElementById("jumpButton");
    const nextUninspectedButton = document.getElementById("nextUninspectedButton");

    function setStatus(message, level = "") {
      statusMessage.textContent = message;
      statusMessage.dataset.level = level;
    }

    function updateChapterButton() {
      if (!state.page) {
        chapterButton.textContent = "Mark end of chapter";
        return;
      }
      chapterButton.textContent = state.page.isChapterEnd ? "Unmark end of chapter" : "Mark end of chapter";
    }

    function updateParagraphToggle() {
      if (!state.page) {
        paragraphToggleInput.checked = false;
        return;
      }
      paragraphToggleInput.checked = state.page.endOfPageIsEndOfParagraph;
    }

    function updateHardPageBreakToggle() {
      if (!state.page) {
        hardPageBreakToggleInput.checked = false;
        return;
      }
      hardPageBreakToggleInput.checked = state.page.hardPageBreak;
    }

    function updatePageMeta() {
      if (!state.page) {
        pageLabel.textContent = "No page loaded";
        imagePathLabel.textContent = "";
        return;
      }

      pageLabel.textContent = `Page ${state.page.pageNumber} • file ${state.page.index + 1} of ${state.page.total}: ${state.page.stem}`;
      imagePathLabel.textContent = state.page.imageFilename;
      inspectedSignal.textContent = state.page.hasManualSave ? "Inspected" : "Not inspected";
      inspectedSignal.dataset.active = state.page.hasManualSave ? "true" : "false";
      savedSignal.textContent = state.isDirty ? "Unsaved" : "Saved";
      savedSignal.dataset.active = state.isDirty ? "false" : "true";
      previousButton.disabled = state.page.index <= 0;
      skipNextButton.disabled = state.page.index >= state.page.total - 1;
      nextButton.disabled = state.page.index >= state.page.total - 1;
      jumpInput.value = String(state.page.pageNumber);
      nextUninspectedButton.disabled = false;
      updateChapterButton();
      updateParagraphToggle();
      updateHardPageBreakToggle();
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
          const payload = await response.json();
          if (payload.error) {
            message = payload.error;
          }
        } catch (error) {
        }
        throw new Error(message);
      }
      return response.json();
    }

    async function loadPage(index) {
      const payload = await fetchJson(`/api/page/${index}`);
      state.page = payload;
      state.index = payload.index;
      state.total = payload.total;
      state.isDirty = false;
      editor.value = payload.text;
      pageImage.src = payload.imageUrl;
      pageImage.alt = payload.imageFilename;
      updatePageMeta();
      editor.focus();
      editor.setSelectionRange(0, 0);
    }

    async function saveCurrentPage({ targetIndex = null, toggleChapter = false } = {}) {
      if (!state.page) {
        return;
      }

      previousButton.disabled = true;
      skipNextButton.disabled = true;
      saveButton.disabled = true;
      nextButton.disabled = true;
      paragraphToggleInput.disabled = true;
      hardPageBreakToggleInput.disabled = true;
      chapterButton.disabled = true;
      jumpButton.disabled = true;

      try {
        const nextChapterState = toggleChapter ? !state.page.isChapterEnd : state.page.isChapterEnd;
        const payload = await fetchJson(`/api/page/${state.index}/save`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: editor.value,
            chapterEnd: nextChapterState
          })
        });

        state.page = payload;
        state.isDirty = false;
        updatePageMeta();
        setStatus(`Saved ${payload.manualFilename}.`, "success");

        if (targetIndex !== null) {
          if (targetIndex < 0 || targetIndex >= state.total) {
            setStatus("Requested page is out of range.", "error");
          } else if (targetIndex !== state.index) {
            await loadPage(targetIndex);
          }
        }
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        previousButton.disabled = false;
        skipNextButton.disabled = false;
        saveButton.disabled = false;
        nextButton.disabled = false;
        paragraphToggleInput.disabled = false;
        hardPageBreakToggleInput.disabled = false;
        jumpButton.disabled = false;
        chapterButton.disabled = false;
        updatePageMeta();
      }
    }

    async function loadAdjacentPageWithoutSaving(targetIndex) {
      if (!state.page) {
        return;
      }
      if (targetIndex < 0 || targetIndex >= state.total) {
        setStatus("Requested page is out of range.", "error");
        return;
      }

      try {
        await loadPage(targetIndex);
      } catch (error) {
        setStatus(error.message, "error");
      }
    }

    async function goToPageNumber() {
      const rawValue = jumpInput.value.trim();
      if (!rawValue) {
        setStatus("Enter a page number to jump to.", "error");
        return;
      }

      try {
        const payload = await fetchJson(`/api/page-number/${encodeURIComponent(rawValue)}`);
        if (payload.index === state.index) {
          setStatus(`Already on page ${payload.pageNumber}.`);
          return;
        }
        await loadPage(payload.index);
      } catch (error) {
        setStatus(error.message, "error");
      }
    }

    async function goToNextUninspectedPage() {
      if (!state.page) {
        return;
      }

      try {
        const payload = await fetchJson(`/api/next-uninspected/${state.index}`);
        if (payload.index === state.index) {
          setStatus("No later uninspected page was found.");
          return;
        }
        await loadPage(payload.index);
      } catch (error) {
        setStatus(error.message, "error");
      }
    }

    async function toggleEndOfParagraph() {
      if (!state.page) {
        return;
      }

      previousButton.disabled = true;
      skipNextButton.disabled = true;
      saveButton.disabled = true;
      nextButton.disabled = true;
      paragraphToggleInput.disabled = true;
      hardPageBreakToggleInput.disabled = true;
      chapterButton.disabled = true;
      jumpButton.disabled = true;

      try {
        const payload = await fetchJson(`/api/page/${state.index}/end-of-page-is-end-of-paragraph`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            value: !state.page.endOfPageIsEndOfParagraph
          })
        });
        state.page = payload;
        updatePageMeta();
        setStatus("Updated end-of-page paragraph toggle.", "success");
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        previousButton.disabled = false;
        skipNextButton.disabled = false;
        saveButton.disabled = false;
        nextButton.disabled = false;
        paragraphToggleInput.disabled = false;
        hardPageBreakToggleInput.disabled = false;
        chapterButton.disabled = false;
        jumpButton.disabled = false;
        updatePageMeta();
      }
    }

    async function toggleHardPageBreak() {
      if (!state.page) {
        return;
      }

      previousButton.disabled = true;
      skipNextButton.disabled = true;
      saveButton.disabled = true;
      nextButton.disabled = true;
      paragraphToggleInput.disabled = true;
      hardPageBreakToggleInput.disabled = true;
      chapterButton.disabled = true;
      jumpButton.disabled = true;

      try {
        const payload = await fetchJson(`/api/page/${state.index}/hard-page-break`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            value: !state.page.hardPageBreak
          })
        });
        state.page = payload;
        updatePageMeta();
        setStatus("Updated hard page break toggle.", "success");
      } catch (error) {
        setStatus(error.message, "error");
      } finally {
        previousButton.disabled = false;
        skipNextButton.disabled = false;
        saveButton.disabled = false;
        nextButton.disabled = false;
        paragraphToggleInput.disabled = false;
        hardPageBreakToggleInput.disabled = false;
        chapterButton.disabled = false;
        jumpButton.disabled = false;
        updatePageMeta();
      }
    }

    editor.addEventListener("input", () => {
      state.isDirty = true;
      updatePageMeta();
    });

    previousButton.addEventListener("click", () => {
      if (!state.page || state.index <= 0) {
        return;
      }
      loadAdjacentPageWithoutSaving(state.index - 1);
    });

    skipNextButton.addEventListener("click", () => {
      if (!state.page || state.index >= state.total - 1) {
        return;
      }
      loadAdjacentPageWithoutSaving(state.index + 1);
    });

    saveButton.addEventListener("click", () => {
      saveCurrentPage();
    });

    nextButton.addEventListener("click", () => {
      if (!state.page) {
        return;
      }
      if (state.index >= state.total - 1) {
        saveCurrentPage();
        return;
      }
      saveCurrentPage({ targetIndex: state.index + 1 });
    });

    paragraphToggleInput.addEventListener("change", () => {
      toggleEndOfParagraph();
    });

    hardPageBreakToggleInput.addEventListener("change", () => {
      toggleHardPageBreak();
    });

    chapterButton.addEventListener("click", () => {
      saveCurrentPage({ toggleChapter: true });
    });

    jumpButton.addEventListener("click", () => {
      goToPageNumber();
    });

    jumpInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        goToPageNumber();
      }
    });

    nextUninspectedButton.addEventListener("click", () => {
      goToNextUninspectedPage();
    });

    document.addEventListener("keydown", (event) => {
      const modifier = event.metaKey || event.ctrlKey;
      if (!modifier) {
        return;
      }

      if (event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveCurrentPage();
        return;
      }

      if (event.shiftKey && event.key === "Enter") {
        event.preventDefault();
        if (!state.page) {
          return;
        }
        if (state.index >= state.total - 1) {
          saveCurrentPage();
          return;
        }
        saveCurrentPage({ targetIndex: state.index + 1 });
        return;
      }

      if (event.shiftKey && event.key === "PageUp") {
        event.preventDefault();
        if (!state.page || state.index <= 0) {
          return;
        }
        loadAdjacentPageWithoutSaving(state.index - 1);
        return;
      }

      if (event.shiftKey && event.key === "PageDown") {
        event.preventDefault();
        if (!state.page || state.index >= state.total - 1) {
          return;
        }
        loadAdjacentPageWithoutSaving(state.index + 1);
        return;
      }

      if (event.shiftKey && event.key.toLowerCase() === "p") {
        event.preventDefault();
        toggleEndOfParagraph();
        return;
      }

      if (event.shiftKey && event.key.toLowerCase() === "l") {
        event.preventDefault();
        toggleHardPageBreak();
      }
    });

    window.addEventListener("beforeunload", (event) => {
      if (!state.isDirty) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    });

    fetchJson("/api/session")
      .then((session) => {
        return loadPage(session.startIndex);
      })
      .catch((error) => {
        setStatus(error.message, "error");
      });
  </script>
</body>
</html>
"""


@dataclass(frozen=True)
class EditorPage:
    index: int
    page_number: int
    stem: str
    image_path: Path
    markdown_path: Path
    manual_path: Path
    diff_path: Path


class ManualEditorState:
    def __init__(self, images_dir: Path, markdown_dir: Path) -> None:
        self.images_dir = images_dir
        self.markdown_dir = markdown_dir
        self.manual_dir = markdown_dir.parent / "manually-fixed"
        self.diff_dir = markdown_dir.parent / "manually-fixed-diffs"
        self.chapter_file = markdown_dir.parent / CHAPTER_ENDS_FILENAME
        self.end_of_page_paragraph_file = markdown_dir.parent / END_OF_PAGE_PARAGRAPH_FILENAME
        self.hard_page_break_file = markdown_dir.parent / HARD_PAGE_BREAK_FILENAME
        self.pages = build_editor_pages(images_dir, markdown_dir, self.manual_dir, self.diff_dir)
        self.manual_dir.mkdir(parents=True, exist_ok=True)
        self.diff_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.chapter_end_stems = self._load_chapter_end_stems()
        self.end_of_page_paragraph_map = self._load_end_of_page_paragraph_map()
        self.hard_page_break_map = self._load_hard_page_break_map()
        self._ensure_hard_page_break_file()
        self.page_by_number = {page.page_number: page for page in self.pages}

    @property
    def start_index(self) -> int:
        return self.find_resume_index()

    def _load_chapter_end_stems(self) -> set[str]:
        if not self.chapter_file.exists():
            return set()

        payload = json.loads(self.chapter_file.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            chapter_end_pages = payload.get("chapter_end_pages", [])
        elif isinstance(payload, list):
            chapter_end_pages = payload
        else:
            raise ValueError(f"Unsupported chapter file format: {self.chapter_file}")

        return {str(item) for item in chapter_end_pages}

    def _write_chapter_file(self) -> None:
        ordered_stems = [page.stem for page in self.pages if page.stem in self.chapter_end_stems]
        payload = {"chapter_end_pages": ordered_stems}
        self.chapter_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _load_end_of_page_paragraph_map(self) -> dict[str, bool]:
        if not self.end_of_page_paragraph_file.exists():
            return {}

        payload = json.loads(self.end_of_page_paragraph_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Unsupported end-of-page paragraph file format: {self.end_of_page_paragraph_file}")
        return {str(key): bool(value) for key, value in payload.items()}

    def _write_end_of_page_paragraph_file(self) -> None:
        ordered_payload = {
            page.stem: self.end_of_page_paragraph_map.get(page.stem, False)
            for page in self.pages
        }
        self.end_of_page_paragraph_file.write_text(
            json.dumps(ordered_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _load_hard_page_break_map(self) -> dict[str, bool]:
        if not self.hard_page_break_file.exists():
            return {}

        payload = json.loads(self.hard_page_break_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Unsupported hard page break file format: {self.hard_page_break_file}")
        return {str(key): bool(value) for key, value in payload.items()}

    def _write_hard_page_break_file(self) -> None:
        ordered_payload = {
            page.stem: self.hard_page_break_map.get(page.stem, False)
            for page in self.pages
        }
        self.hard_page_break_file.write_text(
            json.dumps(ordered_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _ensure_hard_page_break_file(self) -> None:
        for page in self.pages:
            self.hard_page_break_map.setdefault(page.stem, False)
        self._write_hard_page_break_file()

    def get_page(self, index: int) -> EditorPage:
        try:
            return self.pages[index]
        except IndexError as exc:
            raise IndexError(f"Page index out of range: {index}") from exc

    def get_page_by_number(self, page_number: int) -> EditorPage:
        try:
            return self.page_by_number[page_number]
        except KeyError as exc:
            raise KeyError(f"Page number not found: {page_number}") from exc

    def find_resume_index(self) -> int:
        return self.find_next_uninspected_index(start_after=-1)

    def _inspected_stems(self) -> set[str]:
        if not self.manual_dir.exists() or not self.diff_dir.exists():
            return set()

        manual_stems = {
            path.stem
            for path in self.manual_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_MARKDOWN_SUFFIXES
        }
        diff_stems = {path.stem for path in self.diff_dir.iterdir() if path.is_file() and path.suffix.lower() == ".diff"}

        if not manual_stems or manual_stems != diff_stems:
            return set()
        return manual_stems

    def find_next_uninspected_index(self, start_after: int) -> int:
        inspected_stems = self._inspected_stems()

        for page in self.pages[start_after + 1 :]:
            if page.stem not in inspected_stems:
                return page.index

        return start_after if start_after >= 0 else (self.pages[-1].index if self.pages else 0)

    def load_page_text(self, page: EditorPage) -> str:
        source_path = page.manual_path if page.manual_path.exists() else page.markdown_path
        return source_path.read_text(encoding="utf-8")

    def build_session_payload(self) -> dict[str, object]:
        return {
            "startIndex": self.start_index,
            "total": len(self.pages),
        }

    def build_page_payload(self, index: int) -> dict[str, object]:
        page = self.get_page(index)
        return {
            "index": page.index,
            "pageNumber": page.page_number,
            "total": len(self.pages),
            "stem": page.stem,
            "text": self.load_page_text(page),
            "imageUrl": f"/images/{page.index}",
            "imageFilename": page.image_path.name,
            "markdownFilename": page.markdown_path.name,
            "manualFilename": page.manual_path.name,
            "hasManualSave": page.manual_path.exists(),
            "isChapterEnd": page.stem in self.chapter_end_stems,
            "endOfPageIsEndOfParagraph": self.end_of_page_paragraph_map.get(page.stem, False),
            "hardPageBreak": self.hard_page_break_map.get(page.stem, False),
        }

    def save_page(self, index: int, text: str, chapter_end: bool) -> dict[str, object]:
        page = self.get_page(index)
        original_text = page.markdown_path.read_text(encoding="utf-8")

        with self._lock:
            page.manual_path.write_text(text, encoding="utf-8")
            diff_text = build_unified_diff(original_text, text, page.stem)
            write_diff(diff_text, page.diff_path)

            if chapter_end:
                self.chapter_end_stems.add(page.stem)
            else:
                self.chapter_end_stems.discard(page.stem)
            self._write_chapter_file()

        return self.build_page_payload(index)

    def set_end_of_page_paragraph(self, index: int, value: bool) -> dict[str, object]:
        page = self.get_page(index)

        with self._lock:
            self.end_of_page_paragraph_map[page.stem] = value
            self._write_end_of_page_paragraph_file()

        return self.build_page_payload(index)

    def set_hard_page_break(self, index: int, value: bool) -> dict[str, object]:
        page = self.get_page(index)

        with self._lock:
            self.hard_page_break_map[page.stem] = value
            if value:
                self.end_of_page_paragraph_map[page.stem] = True
                self._write_end_of_page_paragraph_file()
            self._write_hard_page_break_file()

        return self.build_page_payload(index)


def build_editor_pages(images_dir: Path, markdown_dir: Path, manual_dir: Path, diff_dir: Path) -> list[EditorPage]:
    if not markdown_dir.exists():
        raise FileNotFoundError(f"Markdown directory does not exist: {markdown_dir}")
    if not markdown_dir.is_dir():
        raise NotADirectoryError(f"Markdown path is not a directory: {markdown_dir}")

    image_paths = collect_image_paths(images_dir)
    markdown_paths = [
        path
        for path in sorted(markdown_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_MARKDOWN_SUFFIXES
    ]
    if not markdown_paths:
        raise ValueError(f"No Markdown files found in {markdown_dir}")

    markdown_by_stem = {path.stem: path for path in markdown_paths}
    pages: list[EditorPage] = []
    missing_stems: list[str] = []

    for index, image_path in enumerate(image_paths):
        markdown_path = markdown_by_stem.get(image_path.stem)
        if markdown_path is None:
            missing_stems.append(image_path.stem)
            continue

        pages.append(
            EditorPage(
                index=index,
                page_number=infer_page_number_from_image_path(image_path, fallback=index + 1),
                stem=image_path.stem,
                image_path=image_path,
                markdown_path=markdown_path,
                manual_path=manual_dir / f"{image_path.stem}.md",
                diff_path=diff_dir / f"{image_path.stem}.diff",
            )
        )

    if missing_stems:
        preview = ", ".join(missing_stems[:5])
        raise ValueError(f"Missing Markdown files for image stems: {preview}")

    return pages


def make_handler(state: ManualEditorState) -> type[BaseHTTPRequestHandler]:
    class ManualEditorHandler(BaseHTTPRequestHandler):
        server_version = "PdfBookDigitizerEditor/0.1"

        def do_GET(self) -> None:  # noqa: N802
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            try:
                if path == "/":
                    self._send_html(EDITOR_HTML)
                    return
                if path == "/api/session":
                    self._send_json(state.build_session_payload())
                    return
                if path.startswith("/api/next-uninspected/"):
                    index = parse_page_index(path, prefix="/api/next-uninspected/")
                    self._send_json(state.build_page_payload(state.find_next_uninspected_index(index)))
                    return
                if path.startswith("/api/page/"):
                    index = parse_page_index(path, prefix="/api/page/")
                    self._send_json(state.build_page_payload(index))
                    return
                if path.startswith("/api/page-number/"):
                    page_number = parse_page_index(path, prefix="/api/page-number/")
                    self._send_json(state.build_page_payload(state.get_page_by_number(page_number).index))
                    return
                if path.startswith("/images/"):
                    index = parse_page_index(path, prefix="/images/")
                    self._send_image(state.get_page(index).image_path)
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def do_POST(self) -> None:  # noqa: N802
            parsed_path = urlparse(self.path)
            path = parsed_path.path

            try:
                if path.startswith("/api/page/") and path.endswith("/hard-page-break"):
                    index = parse_page_index(path.removesuffix("/hard-page-break"), prefix="/api/page/")
                    payload = self._read_json()
                    value = payload.get("value")
                    if not isinstance(value, bool):
                        raise ValueError("Toggle payload must include boolean field 'value'.")
                    self._send_json(state.set_hard_page_break(index, value))
                    return
                if path.startswith("/api/page/") and path.endswith("/end-of-page-is-end-of-paragraph"):
                    index = parse_page_index(
                        path.removesuffix("/end-of-page-is-end-of-paragraph"),
                        prefix="/api/page/",
                    )
                    payload = self._read_json()
                    value = payload.get("value")
                    if not isinstance(value, bool):
                        raise ValueError("Toggle payload must include boolean field 'value'.")
                    self._send_json(state.set_end_of_page_paragraph(index, value))
                    return
                if path.startswith("/api/page/") and path.endswith("/save"):
                    index = parse_page_index(path.removesuffix("/save"), prefix="/api/page/")
                    payload = self._read_json()
                    text = payload.get("text")
                    chapter_end = payload.get("chapterEnd")
                    if not isinstance(text, str):
                        raise ValueError("Save payload must include string field 'text'.")
                    if not isinstance(chapter_end, bool):
                        raise ValueError("Save payload must include boolean field 'chapterEnd'.")
                    self._send_json(state.save_page(index, text, chapter_end))
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            return json.loads(body)

        def _send_html(self, content: str) -> None:
            encoded = content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_image(self, image_path: Path) -> None:
            if not image_path.exists():
                raise FileNotFoundError(f"Image file does not exist: {image_path}")

            content = image_path.read_bytes()
            content_type, _ = mimetypes.guess_type(str(image_path))
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return ManualEditorHandler


def parse_page_index(path: str, prefix: str) -> int:
    page_token = path.removeprefix(prefix).strip("/")
    if not page_token.isdigit():
        raise ValueError(f"Invalid page index: {page_token}")
    return int(page_token)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch a browser-based editor for page images and per-page OCR Markdown."
    )
    parser.add_argument("--images-dir", type=Path, required=True, help="Directory containing one image per page.")
    parser.add_argument(
        "--markdown-dir",
        type=Path,
        required=True,
        help="Directory containing one Markdown file per page.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind the local web server.")
    parser.add_argument("--port", type=int, default=8765, help="Port for the local web server.")
    parser.add_argument(
        "--open-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Open the editor URL in the default browser after the server starts.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    state = ManualEditorState(args.images_dir, args.markdown_dir)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    url = f"http://{args.host}:{args.port}"

    print(f"Serving manual OCR editor at {url}")
    print(f"Images: {args.images_dir}")
    print(f"Markdown: {args.markdown_dir}")
    print(f"Manual output: {state.manual_dir}")
    print(f"Diff output: {state.diff_dir}")
    print(f"Chapter markers: {state.chapter_file}")

    if args.open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping editor.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
