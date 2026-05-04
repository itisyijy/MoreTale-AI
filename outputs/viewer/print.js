const runSelectEl = document.getElementById("print-run-select");
const printTriggerEl = document.getElementById("print-trigger");
const viewerLinkEl = document.getElementById("viewer-link");
const statusEl = document.getElementById("print-status");
const bookTitleEl = document.getElementById("print-book-title");
const bookSubtitleEl = document.getElementById("print-book-subtitle");
const bookPreviewEl = document.getElementById("book-preview");

const state = {
  runs: [],
  book: null,
};

function setStatus(message) {
  statusEl.textContent = message || "";
}

function getRequestedRunId() {
  return new URLSearchParams(window.location.search).get("run")?.trim() || "";
}

function updateRunQuery(runId) {
  const nextUrl = new URL(window.location.href);
  if (runId) {
    nextUrl.searchParams.set("run", runId);
  } else {
    nextUrl.searchParams.delete("run");
  }
  window.history.replaceState({}, "", `${nextUrl.pathname}${nextUrl.search}`);
}

function updateViewerLink() {
  const runId = state.book?.run_id || runSelectEl.value || "";
  viewerLinkEl.href = runId
    ? `/viewer/?run=${encodeURIComponent(runId)}`
    : "/viewer/";
}

function normalizeAspectRatio(value, fallback = "1 / 1") {
  const normalized = String(value || "").trim();
  const match = normalized.match(/^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$/);
  if (!match) {
    return fallback;
  }
  return `${match[1]} / ${match[2]}`;
}

function createIllustrationFigure({ url, aspectRatio, altText, extraClass = "" }) {
  const figure = document.createElement("section");
  figure.className = extraClass ? `print-illustration ${extraClass}` : "print-illustration";
  figure.style.aspectRatio = normalizeAspectRatio(aspectRatio);

  if (!url) {
    const fallback = document.createElement("p");
    fallback.className = "missing-illustration";
    fallback.textContent = "일러스트 없음";
    figure.appendChild(fallback);
    return figure;
  }

  const image = document.createElement("img");
  image.src = url;
  image.alt = altText;
  image.loading = "lazy";
  figure.appendChild(image);
  return figure;
}

function createTextBlock(label, text) {
  const block = document.createElement("section");
  block.className = "print-text-block";

  const blockLabel = document.createElement("p");
  blockLabel.className = "print-text-label";
  blockLabel.textContent = label;

  const paragraph = document.createElement("p");
  paragraph.className = "print-text-paragraph";
  paragraph.textContent = text || "본문이 없습니다.";

  block.appendChild(blockLabel);
  block.appendChild(paragraph);
  return block;
}

function renderCover() {
  const coverUrl = state.book?.assets?.cover?.url;
  if (!coverUrl) {
    return null;
  }

  const coverSheet = document.createElement("article");
  coverSheet.className = "print-sheet print-sheet--cover";

  const frame = document.createElement("div");
  frame.className = "print-sheet__frame print-sheet__frame--cover";

  frame.appendChild(
    createIllustrationFigure({
      url: coverUrl,
      aspectRatio: state.book?.assets?.cover?.aspect_ratio || "5:4",
      altText: "동화 표지 일러스트",
      extraClass: "print-illustration--cover",
    })
  );

  const summary = document.createElement("section");
  summary.className = "print-cover-summary";

  const title = document.createElement("h2");
  title.className = "print-cover-title";
  title.textContent = state.book?.meta?.title_primary || "(제목 없음)";

  const subtitle = document.createElement("p");
  subtitle.className = "print-cover-subtitle";
  subtitle.textContent = state.book?.meta?.title_secondary || "";

  const caption = document.createElement("p");
  caption.className = "print-cover-caption";
  caption.textContent = "표지 다음부터는 A4 세로 1장에 동화 2페이지가 들어가도록 압축된 인쇄 레이아웃입니다.";

  summary.appendChild(title);
  summary.appendChild(subtitle);
  summary.appendChild(caption);

  frame.appendChild(summary);
  coverSheet.appendChild(frame);
  return coverSheet;
}

function renderStoryPage(page, index) {
  const { primary_language: primary, secondary_language: secondary } = state.book.meta;
  const sheet = document.createElement("article");
  sheet.className = "print-sheet print-sheet--story";

  const frame = document.createElement("div");
  frame.className = "print-sheet__frame";

  frame.appendChild(
    createIllustrationFigure({
      url: page.illustration_url,
      aspectRatio: state.book?.assets?.illustrations?.aspect_ratio || "1:1",
      altText: `동화 ${index + 1} 페이지 일러스트`,
    })
  );

  const body = document.createElement("section");
  body.className = "print-sheet__body";

  const meta = document.createElement("div");
  meta.className = "print-sheet__meta";

  const badge = document.createElement("div");
  badge.className = "print-page-badge";
  badge.textContent = String(page.page_number || index + 1);

  const languagePill = document.createElement("div");
  languagePill.className = "print-language-pill";
  languagePill.textContent = `${primary} / ${secondary}`;

  meta.appendChild(badge);
  meta.appendChild(languagePill);

  const textSection = document.createElement("div");
  textSection.className = "print-sheet__text";
  textSection.appendChild(createTextBlock(primary, page.text_primary));
  textSection.appendChild(createTextBlock(secondary, page.text_secondary));

  body.appendChild(meta);
  body.appendChild(textSection);
  frame.appendChild(body);
  sheet.appendChild(frame);

  return sheet;
}

function renderBook() {
  bookPreviewEl.innerHTML = "";

  if (!state.book?.pages?.length) {
    bookPreviewEl.classList.add("hidden");
    return;
  }

  const coverSheet = renderCover();
  if (coverSheet) {
    bookPreviewEl.appendChild(coverSheet);
  }

  state.book.pages.forEach((page, index) => {
    bookPreviewEl.appendChild(renderStoryPage(page, index));
  });

  bookPreviewEl.classList.remove("hidden");
}

function fillRunOptions() {
  runSelectEl.innerHTML = "";

  state.runs.forEach((run) => {
    const option = document.createElement("option");
    option.value = run.id;
    option.textContent = `${run.title_primary || run.id} (${run.page_count}p)`;
    runSelectEl.appendChild(option);
  });
}

async function loadBook(runId) {
  setStatus("책 미리보기를 불러오는 중...");
  printTriggerEl.disabled = true;
  bookPreviewEl.classList.add("hidden");
  state.book = null;
  updateRunQuery(runId);
  updateViewerLink();

  try {
    const response = await fetch(`/api/book?run=${encodeURIComponent(runId)}`);
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.error || `HTTP ${response.status}`);
    }

    state.book = await response.json();
    bookTitleEl.textContent = state.book.meta.title_primary || "동화 책 미리보기";
    bookSubtitleEl.textContent = state.book.meta.title_secondary || "";
    document.title = `${state.book.meta.title_primary || "Story"} | MoreTale Print Book`;
    updateViewerLink();
    renderBook();
    printTriggerEl.disabled = false;
    setStatus("");
  } catch (error) {
    console.error("Failed to load print book", error);
    state.book = null;
    bookTitleEl.textContent = "동화 책 미리보기";
    bookSubtitleEl.textContent = "";
    updateViewerLink();
    bookPreviewEl.innerHTML = "";
    bookPreviewEl.classList.add("hidden");
    setStatus(`불러오기 실패: ${error.message}`);
  }
}

async function loadRuns() {
  setStatus("실행 결과 목록 불러오는 중...");
  printTriggerEl.disabled = true;
  state.book = null;
  updateViewerLink();

  try {
    const response = await fetch("/api/runs");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    state.runs = payload.runs || [];

    if (state.runs.length <= 0) {
      runSelectEl.innerHTML = "";
      setStatus("표시할 스토리 결과가 없습니다.");
      return;
    }

    fillRunOptions();

    const requestedRunId = getRequestedRunId();
    const initialRun =
      state.runs.find((run) => run.id === requestedRunId) || state.runs[0];

    runSelectEl.value = initialRun.id;
    await loadBook(initialRun.id);
  } catch (error) {
    console.error("Failed to load print runs", error);
    setStatus(`목록 로딩 실패: ${error.message}`);
  }
}

runSelectEl.addEventListener("change", (event) => {
  const runId = event.target.value;
  if (!runId) {
    return;
  }
  loadBook(runId);
});

printTriggerEl.addEventListener("click", () => {
  window.print();
});

updateViewerLink();
loadRuns();
