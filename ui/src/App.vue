<template>
  <main class="page">
    <header class="hero">
      <div class="branding">
        <img
          class="logo"
          src="https://img.icons8.com/nolan/64/web-analystics.png"
          alt="AWS"
        />
        <div>
          <h1>DataWeaver</h1>
          <p class="subtitle">Upload data, ask questions, get AI-driven insights.</p>
        </div>
      </div>
    </header>

    <section class="card">
      <h2>Upload Data Sources</h2>
      <p class="hint">Select up to 5 files (CSV, Excel, Parquet, or JSON).</p>

      <div
        class="dropzone"
        :class="{ 'dropzone--active': isDragging }"
        @dragenter.prevent="onDragEnter"
        @dragover.prevent="onDragOver"
        @dragleave.prevent="onDragLeave"
        @drop.prevent="onDrop"
      >
        <input
          id="file-input"
          ref="fileInput"
          multiple
          type="file"
          accept=".csv,.xlsx,.xls,.parquet,.json"
          :disabled="isUploading"
          @change="handleFileSelection"
        />
        <div class="dropzone__content">
          <div class="dropzone__icon" aria-hidden="true">
            <img class="dropzone__image" src="/icons/upload.svg" alt="" />
          </div>
          <p class="dropzone__title">Drag &amp; drop files here</p>
          <p class="dropzone__subtitle">or click to browse your computer</p>
          <p class="dropzone__types">CSV, Excel, Parquet, JSON &middot; Max 5 files</p>
          <button
            type="button"
            class="dropzone__button"
            :disabled="isUploading"
            @click.prevent="triggerFileDialog"
          >
            Browse Files
          </button>
        </div>
      </div>

      <transition name="fade">
        <ul v-if="selectedFiles.length" class="file-list">
          <li v-for="file in selectedFiles" :key="file.name">
            <span class="file-name">{{ file.name }}</span>
            <span class="file-size">{{ formatSize(file.size) }}</span>
          </li>
        </ul>
      </transition>

      <div class="button-row">
        <button
          class="primary upload-button"
          :disabled="!selectedFiles.length || isUploading"
          @click="uploadSelectedFiles"
        >
          <span class="btn-icon" aria-hidden="true">
            <img src="/icons/cloud-upload.svg" alt="" />
          </span>
          <span class="btn-label">
            {{ isUploading ? "Uploading..." : "Upload to S3" }}
          </span>
        </button>
      </div>

      <div v-if="uploadedFiles.length" class="uploaded">
        <h3>Uploaded Files</h3>
        <ul>
          <li v-for="item in uploadedFiles" :key="item.name">
            <span class="file-name">{{ item.name }}</span>
            <code>{{ item.s3Uri }}</code>
          </li>
        </ul>
      </div>
    </section>

    <section class="card">
      <h2>Ask a Question</h2>
      <textarea
        v-model="prompt"
        class="prompt-input"
        placeholder="Describe the analysis you want to run..."
        rows="8"
      ></textarea>
      <div class="actions">
        <button
          class="primary"
          :disabled="!isReadyToAnalyze || isAnalyzing"
          @click="runAnalysis"
        >
          <span class="btn-icon" aria-hidden="true">
            <img src="/icons/sparkle.svg" alt="" />
          </span>
          <span class="btn-label">
            {{ isAnalyzing ? "Analyzing..." : "Run Analysis" }}
          </span>
        </button>
        <button class="ghost" :disabled="isAnalyzing" @click="reset">
          Clear
        </button>
      </div>
      <p class="caption">The backend will use Amazon Bedrock AgentCore runtime for analysis.</p>
    </section>

<!--    <section class="card">-->
<!--      <h2>Observability</h2>-->
<!--      <p class="hint">-->
<!--        Optional tracing context. Leave blank for defaults.-->
<!--      </p>-->
<!--      <div class="grid">-->
<!--        <label class="field">-->
<!--          <span>Session ID</span>-->
<!--          <input-->
<!--            type="text"-->
<!--            placeholder="X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"-->
<!--            v-model="traceFields.sessionId"-->
<!--          />-->
<!--        </label>-->
<!--        <label class="field">-->
<!--          <span>MCP Session ID</span>-->
<!--          <input-->
<!--            type="text"-->
<!--            placeholder="mcp-session-id"-->
<!--            v-model="traceFields.mcpSessionId"-->
<!--          />-->
<!--        </label>-->
<!--        <label class="field">-->
<!--          <span>Traceparent</span>-->
<!--          <input-->
<!--            type="text"-->
<!--            placeholder="00-4bf92f...-00f067aa0ba902b7-01"-->
<!--            v-model="traceFields.traceparent"-->
<!--          />-->
<!--        </label>-->
<!--        <label class="field">-->
<!--          <span>Tracestate</span>-->
<!--          <input-->
<!--            type="text"-->
<!--            placeholder="congo=t61rcWkgMzE,rojo=00f067aa0ba902b7"-->
<!--            v-model="traceFields.tracestate"-->
<!--          />-->
<!--        </label>-->
<!--        <label class="field">-->
<!--          <span>Baggage</span>-->
<!--          <input-->
<!--            type="text"-->
<!--            placeholder="userId=alice,serverRegion=us-east-1"-->
<!--            v-model="traceFields.baggage"-->
<!--          />-->
<!--        </label>-->
<!--        <label class="field">-->
<!--          <span>X-Ray Trace ID</span>-->
<!--          <input-->
<!--            type="text"-->
<!--            placeholder="Root=1-5759e988-..."-->
<!--            v-model="traceFields.traceId"-->
<!--          />-->
<!--        </label>-->
<!--      </div>-->
<!--    </section>-->

    <section v-if="analysisResult" class="card">
      <h2>Results</h2>
      <div class="analysis-output">
        <div
          v-if="renderedOutput"
          class="analysis-markdown"
          v-html="renderedOutput"
        ></div>
        <p v-else class="analysis-placeholder">No output returned.</p>
      </div>

      <div v-if="resolvedCharts.length" class="charts-section">
        <h3>Charts</h3>
        <div class="chart-grid">
          <article
            v-for="(chartUrl, index) in resolvedCharts"
            :key="`${chartUrl}-${index}`"
            class="chart-card"
          >
            <img
              :src="chartUrl"
              :alt="`Generated chart ${index + 1}`"
              class="chart-image"
              loading="lazy"
            />
            <a
              :href="chartUrl"
              target="_blank"
              rel="noopener"
              class="chart-link"
            >
              Open chart {{ index + 1 }}
            </a>
          </article>
        </div>
      </div>

      <details v-if="structuredSteps.length" class="steps-accordion">
        <summary>
          <span>Intermediate Steps</span>
          <span class="badge">{{ structuredSteps.length }}</span>
        </summary>
        <ol class="steps-list">
          <li v-for="step in structuredSteps" :key="step.index">
            <header class="step-header">
              <span class="step-number">Step {{ step.index + 1 }}</span>
              <span v-if="step.action?.tool" class="step-tool">{{ step.action.tool }}</span>
            </header>
            <div class="step-body">
              <p v-if="step.action?.log" class="step-log">{{ step.action.log }}</p>
              <div v-if="step.action?.tool_input" class="step-field">
                <span class="field-label">Action Input</span>
                <pre>{{ step.action.tool_input }}</pre>
              </div>
              <div
                v-if="step.observation !== undefined && step.observation !== null && step.observation !== ''"
                class="step-field"
              >
                <span class="field-label">Observation</span>
                <pre>{{ formatObservation(step.observation) }}</pre>
              </div>
            </div>
          </li>
        </ol>
      </details>

      <p v-if="analysisResult.dataframes_loaded?.length" class="caption">
        Dataframes analyzed: {{ analysisResult.dataframes_loaded.join(", ") }}
      </p>
    </section>

    <section v-if="errorMessage" class="card error">
      <h2>Error</h2>
      <p>{{ errorMessage }}</p>
    </section>
  </main>
</template>

<script setup>
import { computed, ref } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { apiClient } from "./apiClient.js";

const selectedFiles = ref([]);
const uploadedFiles = ref([]);
const prompt = ref("");
const isUploading = ref(false);
const isAnalyzing = ref(false);
const analysisResult = ref(null);
const errorMessage = ref("");

const fileInput = ref(null);
const dragCounter = ref(0);
const isDragging = computed(() => dragCounter.value > 0);

const triggerFileDialog = () => {
  fileInput.value?.click();
};

const normalizeFiles = (fileList) => {
  const files = Array.from(fileList || []);
  if (files.length > 5) {
    return files.slice(0, 5);
  }
  return files;
};

const handleFileSelection = (event) => {
  selectedFiles.value = normalizeFiles(event.target.files);
};

const onDragEnter = () => {
  dragCounter.value += 1;
};

const onDragOver = () => {
  dragCounter.value = Math.max(dragCounter.value, 1);
};

const onDragLeave = () => {
  dragCounter.value = Math.max(dragCounter.value - 1, 0);
};

const onDrop = (event) => {
  dragCounter.value = 0;
  const files = normalizeFiles(event.dataTransfer.files);
  if (files.length) {
    selectedFiles.value = files;
  }
};

const formatSize = (bytes) => {
  if (!bytes && bytes !== 0) {
    return "";
  }
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

const uploadSelectedFiles = async () => {
  if (!selectedFiles.value.length) {
    return;
  }

  const formData = new FormData();
  selectedFiles.value.forEach((file) => formData.append("files", file));

  isUploading.value = true;
  errorMessage.value = "";

  try {
    const response = await apiClient.post("/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });

    const { s3_urls: s3Urls = {} } = response.data;
    uploadedFiles.value = Object.entries(s3Urls).map(([name, s3Uri]) => ({
      name,
      s3Uri
    }));
  } catch (error) {
    errorMessage.value = resolveErrorMessage(error, "Failed to upload files.");
  } finally {
    isUploading.value = false;
  }
};

const isReadyToAnalyze = computed(() => {
  return uploadedFiles.value.length > 0 && prompt.value.trim().length > 0;
});

const traceFields = ref({
  traceId: "",
  traceparent: "",
  tracestate: "",
  baggage: "",
  sessionId: "",
  mcpSessionId: "",
});

const resetTraceFields = () => {
  traceFields.value = {
    traceId: "",
    traceparent: "",
    tracestate: "",
    baggage: "",
    sessionId: "",
    mcpSessionId: "",
  };
};

const generateSessionId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, "");
  }

  const randomSegment = () => Math.random().toString(36).slice(2);
  let candidate = "";
  while (candidate.length <= 32) {
    candidate += randomSegment();
  }
  return candidate.slice(0, 64);
};

const ensureRuntimeSessionId = () => {
  const existing = (traceFields.value.sessionId || "").trim();
  if (existing.length > 32) {
    return existing;
  }

  const sessionId = generateSessionId();
  traceFields.value.sessionId = sessionId;
  return sessionId;
};

const observabilityHeaders = computed(() => {
  const headers = {};
  if (traceFields.value.sessionId) {
    headers["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"] = traceFields.value.sessionId;
  }
  if (traceFields.value.mcpSessionId) {
    headers["mcp-session-id"] = traceFields.value.mcpSessionId;
  }
  if (traceFields.value.traceparent) {
    headers["traceparent"] = traceFields.value.traceparent;
  }
  if (traceFields.value.tracestate) {
    headers["tracestate"] = traceFields.value.tracestate;
  }
  if (traceFields.value.baggage) {
    headers["baggage"] = traceFields.value.baggage;
  }
  if (traceFields.value.traceId) {
    headers["X-Amzn-Trace-Id"] = traceFields.value.traceId;
  }
  return headers;
});

const runAnalysis = async () => {
  if (!isReadyToAnalyze.value) {
    return;
  }

  isAnalyzing.value = true;
  errorMessage.value = "";

  const s3UrlsPayload = uploadedFiles.value.reduce((acc, item) => {
    acc[item.name] = item.s3Uri;
    return acc;
  }, {});

  const runtimeSessionId = ensureRuntimeSessionId();

  try {
    const response = await apiClient.post(
      "/chat",
      {
        s3_urls: s3UrlsPayload,
        prompt: prompt.value,
        traceId: traceFields.value.traceId || undefined,
        traceparent: traceFields.value.traceparent || undefined,
        tracestate: traceFields.value.tracestate || undefined,
        baggage: traceFields.value.baggage || undefined,
      },
      {
        headers: {
          ...observabilityHeaders.value,
          "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": runtimeSessionId,
        },
      }
    );
    analysisResult.value = response.data;
  } catch (error) {
    analysisResult.value = null;
    errorMessage.value = resolveErrorMessage(error, "Analysis failed.");
  } finally {
    isAnalyzing.value = false;
  }
};

const reset = () => {
  selectedFiles.value = [];
  uploadedFiles.value = [];
  analysisResult.value = null;
  prompt.value = "";
  errorMessage.value = "";
  resetTraceFields();
};

const resolvedCharts = computed(() => {
  const charts = analysisResult.value?.charts;
  if (Array.isArray(charts)) {
    return charts.filter((item) => typeof item === "string" && item.trim()).map((item) => item.trim());
  }
  if (typeof charts === "string" && charts.trim()) {
    return [charts.trim()];
  }
  return [];
});

const renderedOutput = computed(() => {
  const output = analysisResult.value?.output;
  if (!output) {
    return "";
  }

  const text =
    typeof output === "string"
      ? output
      : (() => {
          try {
            return JSON.stringify(output, null, 2);
          } catch {
            return String(output);
          }
        })();

  const rawHtml = marked.parse(text, {
    mangle: false,
    headerIds: false,
    breaks: true,
  });

  return DOMPurify.sanitize(rawHtml);
});

const structuredSteps = computed(() => {
  const rawSteps = analysisResult.value?.intermediate_steps;
  if (!Array.isArray(rawSteps)) {
    return [];
  }

  return rawSteps.map((entry, index) => {
    let action = null;
    let observation = null;

    if (Array.isArray(entry)) {
      if (entry.length > 0 && entry[0] && typeof entry[0] === "object") {
        action = entry[0];
      }
      if (entry.length > 1) {
        observation = entry[1];
      }
    } else if (entry && typeof entry === "object") {
      action = entry;
    } else {
      observation = entry;
    }

    return {
      index,
      action,
      observation,
    };
  });
});

const formatObservation = (value) => {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch (error) {
    return String(value);
  }
};

const resolveErrorMessage = (error, fallback) => {
  if (error.response?.data?.detail) {
    return typeof error.response.data.detail === "string"
      ? error.response.data.detail
      : JSON.stringify(error.response.data.detail);
  }
  if (error.message) {
    return error.message;
  }
  return fallback;
};
</script>

<style scoped>
.page {
  max-width: 960px;
  margin: 0 auto;
  padding: 3rem 1.5rem 4rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.hero {
  padding: 0 0 1.5rem 0;
  color: #1e293b;
}

.branding {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.logo {
  width: 56px;
  height: 56px;
}

.branding h1 {
  color: #1d4ed8;
  font-weight: 600;
}

.subtitle {
  margin: 0.25rem 0 0;
  font-size: 1rem;
  color: #475569;
}

.card {
  background-color: #fff;
  border-radius: 16px;
  padding: 1.75rem;
  box-shadow: 0 16px 32px -24px rgba(15, 23, 42, 0.35);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  box-sizing: border-box;
}

.card.error {
  border: 1px solid #dc2626;
}

h1,
h2,
h3 {
  margin: 0;
}

.hint {
  margin: 0;
  color: #475569;
}

.dropzone {
  position: relative;
  border: 2px dashed #cbd5f5;
  border-radius: 18px;
  padding: 2.5rem 1rem;
  background: linear-gradient(180deg, #f8fbff, #eef3ff);
  text-align: center;
  transition: border-color 0.25s ease, transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.dropzone input[type="file"] {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.dropzone--active {
  border-color: #2563eb;
  transform: translateY(-2px);
  box-shadow: 0 18px 40px -28px rgba(37, 99, 235, 0.7);
}

.dropzone__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  color: #1e293b;
  text-align: center;
}

.dropzone__icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 56px;
  height: 56px;
}

.dropzone__image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.dropzone__title {
  font-size: 1.2rem;
  font-weight: 600;
  margin: 0;
}

.dropzone__subtitle {
  margin: 0;
  color: #475569;
}

.dropzone__types {
  margin: 0.25rem 0 0;
  font-size: 0.9rem;
  color: #1d4ed8;
}

.dropzone__button {
  pointer-events: auto;
  margin-top: 1rem;
  padding: 0.65rem 1.5rem;
  border-radius: 999px;
  background: #1d4ed8;
  color: #fff;
  border: none;
  font-weight: 600;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.dropzone__button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px -18px rgba(29, 78, 216, 0.8);
}

.file-list {
  margin: 0;
  padding: 0;
  list-style: none;
  background-color: #f8fafc;
  border-radius: 16px;
  padding: 1rem 1.25rem;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.file-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.95rem;
  color: #1e293b;
}

.file-name {
  font-weight: 600;
  color: #0f172a;
}

.file-size {
  color: #475569;
  font-size: 0.85rem;
}

.button-row {
  width: 100%;
  display: flex;
  justify-content: flex-end;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.prompt-input {
  width: 100%;
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid #cbd5f5;
  font-size: 1rem;
  resize: vertical;
  font-family: inherit;
  background-color: #f8fafc;
  box-sizing: border-box;
}

.prompt-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.95rem;
  color: #1e293b;
}

.field input {
  border-radius: 10px;
  border: 1px solid #d0d7f0;
  padding: 0.65rem 0.8rem;
  font-size: 0.95rem;
  background-color: #f8fbff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.field input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
  background-color: #fff;
}

.actions {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
}

button {
  border: none;
  border-radius: 999px;
  padding: 0.75rem 1.75rem;
  font-size: 1rem;
  font-weight: 600;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
  background-color: #e2e8f0;
  color: #0f172a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}

.primary {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #fff;
  box-shadow: 0 10px 18px -12px rgba(37, 99, 235, 0.6);
}

.primary:not(:disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 22px -10px rgba(37, 99, 235, 0.65);
}

.ghost {
  background-color: transparent;
  border: 1px solid #cbd5f5;
}

.btn-icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-icon img {
  width: 100%;
  height: 100%;
  display: block;
  filter: drop-shadow(0 0 0 transparent);
}

.btn-label {
  white-space: nowrap;
}

.analysis-output {
  background-color: #f8fafc;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  padding: 1.5rem;
  font-size: 0.97rem;
  color: #0f172a;
  overflow-x: auto;
  box-shadow: 0 16px 30px -28px rgba(15, 23, 42, 0.6);
}

.analysis-markdown {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  line-height: 1.6;
}

.analysis-markdown h1,
.analysis-markdown h2,
.analysis-markdown h3,
.analysis-markdown h4,
.analysis-markdown h5,
.analysis-markdown h6 {
  margin: 0;
  font-weight: 600;
  color: #1e293b;
}

.analysis-markdown h2 {
  font-size: 1.35rem;
}

.analysis-markdown h3 {
  font-size: 1.1rem;
}

.analysis-markdown p {
  margin: 0;
}

.analysis-markdown ul,
.analysis-markdown ol {
  margin: 0;
  padding-left: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.analysis-markdown li {
  margin: 0;
}

.analysis-markdown code {
  background-color: #e2e8f0;
  padding: 0.15rem 0.35rem;
  border-radius: 6px;
  font-size: 0.92rem;
}

.analysis-markdown pre {
  margin: 0;
  background-color: #0f172a;
  color: #e2e8f0;
  padding: 1rem 1.25rem;
  border-radius: 12px;
  overflow-x: auto;
}

.analysis-markdown table {
  border-collapse: collapse;
  font-size: 0.95rem;
  align-self: flex-start;
  max-width: 100%;
}

.analysis-markdown th,
.analysis-markdown td {
  border: 1px solid #dbe4ff;
  padding: 0.55rem 0.9rem;
  text-align: left;
  white-space: nowrap;
}

.analysis-markdown th {
  background-color: #eef2ff;
  font-weight: 600;
}

.analysis-placeholder {
  margin: 0;
  color: #64748b;
  font-style: italic;
}

.charts-section {
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.charts-section h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #1e293b;
}

.chart-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.chart-card {
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  align-items: center;
  box-shadow: 0 10px 24px -22px rgba(15, 23, 42, 0.45);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.chart-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 30px -20px rgba(37, 99, 235, 0.35);
}

.chart-image {
  width: 100%;
  height: auto;
  max-height: 260px;
  border-radius: 10px;
  object-fit: contain;
  background-color: #fff;
}

.chart-link {
  font-weight: 600;
  color: #1d4ed8;
  text-decoration: none;
}

.chart-link:hover {
  text-decoration: underline;
}

.steps-accordion {
  background-color: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 1rem 1.25rem;
  margin-top: 1rem;
}

.steps-accordion[open] {
  box-shadow: 0 8px 24px -18px rgba(30, 64, 175, 0.35);
}

.steps-accordion summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  list-style: none;
  font-weight: 600;
  cursor: pointer;
  color: #1e293b;
}

.steps-accordion summary::-webkit-details-marker {
  display: none;
}

.badge {
  background-color: #2563eb;
  color: #fff;
  border-radius: 999px;
  padding: 0.1rem 0.6rem;
  font-size: 0.8rem;
}

.steps-list {
  margin: 1rem 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.steps-list li {
  background-color: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 1rem;
  box-shadow: 0 12px 24px -24px rgba(15, 23, 42, 0.4);
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.step-number {
  font-weight: 600;
  color: #1d4ed8;
}

.step-tool {
  background-color: #e0e7ff;
  color: #1d4ed8;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.85rem;
}

.step-body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.step-log {
  margin: 0;
  background-color: #eef2ff;
  color: #1e3a8a;
  border-radius: 10px;
  padding: 0.75rem;
  white-space: pre-wrap;
}

.step-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field-label {
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #475569;
}

.step-field pre {
  margin: 0;
  background-color: #0f172a;
  color: #e0f2fe;
  border-radius: 10px;
  padding: 0.75rem;
  white-space: pre-wrap;
  overflow-x: auto;
}

.details {
  background-color: #f1f5f9;
  border-radius: 12px;
  padding: 1rem;
  overflow-x: auto;
}

.details pre {
  margin: 0;
  white-space: pre-wrap;
  font-size: 0.9rem;
}

.caption {
  margin: 0;
  color: #64748b;
  font-size: 0.9rem;
}

@media (max-width: 720px) {
  .hero {
    padding: 1.5rem;
  }

  .card {
    padding: 1.5rem;
  }

  .button-row,
  .actions {
    justify-content: stretch;
  }

  .actions {
    flex-direction: column;
    align-items: stretch;
  }

  button {
    width: 100%;
  }
}
</style>
