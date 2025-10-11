import axios from "axios";

const envBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").trim();
const runtimeBaseUrl =
  typeof window !== "undefined" ? window.__AGENT_CORE_API_BASE_URL : "";

const pickBaseUrl = () => {
  const candidate =
    envBaseUrl ||
    (typeof runtimeBaseUrl === "string" ? runtimeBaseUrl.trim() : "");

  if (candidate) {
    return candidate.replace(/\/+$/, "");
  }

  return "http://localhost:8080";
};

export const apiClient = axios.create({
  baseURL: pickBaseUrl(),
});
