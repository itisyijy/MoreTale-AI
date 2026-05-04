const quizRunSelectEl = document.getElementById("quiz-run-select");
const quizStatusEl = document.getElementById("quiz-status");
const quizTitleEl = document.getElementById("quiz-title");
const quizSubtitleEl = document.getElementById("quiz-subtitle");
const quizSummaryEl = document.getElementById("quiz-summary");
const quizListEl = document.getElementById("quiz-list");
const quizEmptyEl = document.getElementById("quiz-empty");
const storyViewLinkEl = document.getElementById("story-view-link");
const quizJsonLinkEl = document.getElementById("quiz-json-link");

const quizState = {
  runs: [],
  runId: "",
  quiz: null,
};

const SKILL_LABELS = {
  story_comprehension: "내용 이해",
  cause_and_effect: "원인과 결과",
  character_emotion: "인물 감정",
  sequence: "순서",
  vocabulary_in_context: "단어 맥락",
};

function setQuizStatus(message) {
  quizStatusEl.textContent = message || "";
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

function updateLinks(runId, quizJsonUrl = null) {
  storyViewLinkEl.href = runId
    ? `/viewer/?run=${encodeURIComponent(runId)}`
    : "/viewer/";

  if (quizJsonUrl) {
    quizJsonLinkEl.href = quizJsonUrl;
    quizJsonLinkEl.classList.remove("hidden");
  } else {
    quizJsonLinkEl.href = "#";
    quizJsonLinkEl.classList.add("hidden");
  }
}

function hideQuizContent() {
  quizSummaryEl.classList.add("hidden");
  quizListEl.classList.add("hidden");
  quizEmptyEl.classList.add("hidden");
}

function fillRunOptions(runs) {
  quizRunSelectEl.innerHTML = "";

  runs.forEach((run) => {
    const option = document.createElement("option");
    option.value = run.id;

    const title = run.title_primary || run.id;
    const quizMarker = run.has_quiz ? "퀴즈 있음" : "퀴즈 없음";
    option.textContent = `${title} (${run.page_count}p, ${quizMarker})`;
    quizRunSelectEl.appendChild(option);
  });
}

function makeChip(text, className = "") {
  const chip = document.createElement("span");
  chip.className = className ? `quiz-chip ${className}` : "quiz-chip";
  chip.textContent = text;
  return chip;
}

function renderSummary(quiz) {
  quizSummaryEl.innerHTML = "";

  const items = [
    ["문항 수", `${quiz.question_count || quiz.questions?.length || 0}개`],
    ["Primary", quiz.primary_language || "-"],
    ["Secondary", quiz.secondary_language || "-"],
  ];

  items.forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "quiz-summary-item";

    const labelEl = document.createElement("span");
    labelEl.textContent = label;

    const valueEl = document.createElement("strong");
    valueEl.textContent = value;

    item.append(labelEl, valueEl);
    quizSummaryEl.appendChild(item);
  });

  quizSummaryEl.classList.remove("hidden");
}

function renderChoices(question) {
  const choicesEl = document.createElement("ol");
  choicesEl.className = "quiz-choices";

  const answerId = question.answer?.choice_id;
  (question.choices || []).forEach((choice) => {
    const choiceEl = document.createElement("li");
    choiceEl.className = "quiz-choice";
    choiceEl.classList.toggle("is-answer", choice.choice_id === answerId);

    const marker = document.createElement("span");
    marker.className = "quiz-choice-marker";
    marker.textContent = choice.choice_id;

    const text = document.createElement("span");
    text.className = "quiz-choice-text";
    text.textContent = choice.text || "";

    choiceEl.append(marker, text);
    choicesEl.appendChild(choiceEl);
  });

  return choicesEl;
}

function renderQuestion(question, index) {
  const article = document.createElement("article");
  article.className = "quiz-question-card";

  const head = document.createElement("div");
  head.className = "quiz-question-head";

  const number = document.createElement("span");
  number.className = "quiz-question-number";
  number.textContent = `Q${index + 1}`;

  const skill = makeChip(SKILL_LABELS[question.skill] || question.skill || "문항");
  skill.classList.add("quiz-skill");

  head.append(number, skill);

  const title = document.createElement("h2");
  title.className = "quiz-question-text";
  title.textContent = question.question_text || "";

  const answer = document.createElement("p");
  answer.className = "quiz-answer";
  answer.textContent = `정답: ${question.answer?.choice_id || "-"} ${question.answer?.text || ""}`.trim();

  const explanation = document.createElement("p");
  explanation.className = "quiz-explanation";
  explanation.textContent = question.explanation || "";

  const sources = document.createElement("div");
  sources.className = "quiz-sources";
  (question.source_page_numbers || []).forEach((pageNumber) => {
    sources.appendChild(makeChip(`${pageNumber}페이지`, "quiz-source-chip"));
  });
  (question.source_vocabulary_entry_ids || []).forEach((entryId) => {
    sources.appendChild(makeChip(`단어: ${entryId}`, "quiz-vocab-chip"));
  });

  article.append(head, title, renderChoices(question), answer, explanation);
  if (sources.childElementCount > 0) {
    article.appendChild(sources);
  }

  return article;
}

function renderQuiz(payload) {
  const quiz = payload.quiz;
  quizState.quiz = quiz;
  hideQuizContent();
  updateLinks(payload.run_id, payload.quiz_json_url);

  if (!quiz) {
    quizTitleEl.textContent = "퀴즈 없음";
    quizSubtitleEl.textContent = payload.run_id || "";
    document.title = "퀴즈 없음 | MoreTale Quiz Viewer";
    quizEmptyEl.classList.remove("hidden");
    return;
  }

  const title = quiz.story_title_primary || "퀴즈";
  const subtitle = quiz.story_title_secondary || payload.run_id || "";
  quizTitleEl.textContent = title;
  quizSubtitleEl.textContent = subtitle;
  document.title = `${title} 퀴즈 | MoreTale Quiz Viewer`;

  renderSummary(quiz);
  quizListEl.innerHTML = "";
  (quiz.questions || []).forEach((question, index) => {
    quizListEl.appendChild(renderQuestion(question, index));
  });
  quizListEl.classList.remove("hidden");
}

async function loadQuiz(runId) {
  setQuizStatus("퀴즈 불러오는 중...");
  hideQuizContent();
  quizState.runId = runId;
  quizState.quiz = null;
  updateRunQuery(runId);
  updateLinks(runId);

  try {
    const response = await fetch(`/api/quiz?run=${encodeURIComponent(runId)}`);
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.error || `HTTP ${response.status}`);
    }

    const payload = await response.json();
    setQuizStatus("");
    renderQuiz(payload);
  } catch (error) {
    console.error("Failed to load quiz", error);
    setQuizStatus(`퀴즈 로딩 실패: ${error.message}`);
    quizTitleEl.textContent = "퀴즈";
    quizSubtitleEl.textContent = runId;
    updateLinks(runId);
  }
}

async function loadRuns() {
  setQuizStatus("실행 결과 목록 불러오는 중...");
  hideQuizContent();
  updateLinks("");

  try {
    const response = await fetch("/api/runs");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    quizState.runs = payload.runs || [];

    if (quizState.runs.length === 0) {
      quizRunSelectEl.innerHTML = "";
      setQuizStatus("표시할 스토리 결과가 없습니다.");
      return;
    }

    fillRunOptions(quizState.runs);

    const requestedRunId = getRequestedRunId();
    const initialRun =
      quizState.runs.find((run) => run.id === requestedRunId) ||
      quizState.runs.find((run) => run.has_quiz) ||
      quizState.runs[0];

    quizRunSelectEl.value = initialRun.id;
    await loadQuiz(initialRun.id);
  } catch (error) {
    console.error("Failed to load runs", error);
    setQuizStatus(`목록 로딩 실패: ${error.message}`);
  }
}

quizRunSelectEl.addEventListener("change", (event) => {
  const runId = event.target.value;
  if (!runId) {
    return;
  }
  loadQuiz(runId);
});

loadRuns();
