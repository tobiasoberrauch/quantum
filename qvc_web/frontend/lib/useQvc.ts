"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import type { Artifact, Job, JobSummary, LogRec, Status, TraceRec } from "./types";

export interface ActiveJob {
  id: string; kind: string; status: string;
  error?: string | null; started?: number; created?: number;
}

export function useQvc() {
  const [status, setStatus] = useState<Status | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [trace, setTrace] = useState<TraceRec[]>([]);
  const [logs, setLogs] = useState<LogRec[]>([]);
  const [lastResult, setLastResult] = useState<{ kind: string; result: any } | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshStatus = useCallback(async () => { try { setStatus(await api.get<Status>("/status")); } catch { /* ignore */ } }, []);
  const refreshJobs = useCallback(async () => { try { setJobs((await api.get<{ jobs: JobSummary[] }>("/jobs")).jobs); } catch { /* ignore */ } }, []);
  const refreshArtifacts = useCallback(async () => { try { setArtifacts((await api.get<{ files: Artifact[] }>("/artifacts")).files); } catch { /* ignore */ } }, []);

  useEffect(() => { refreshStatus(); refreshJobs(); refreshArtifacts(); }, [refreshStatus, refreshJobs, refreshArtifacts]);

  const stopPolling = useCallback(() => { if (timer.current) { clearInterval(timer.current); timer.current = null; } }, []);

  const tick = useCallback(async (id: string) => {
    try {
      const job = await api.get<Job>(`/jobs/${id}`);
      const [tr, lg] = await Promise.all([
        api.get<{ trace: TraceRec[] }>("/trace"),
        api.get<{ logs: LogRec[] }>("/logs"),
      ]);
      setTrace(tr.trace);
      setLogs(lg.logs);
      setActiveJob({ id: job.id, kind: job.kind, status: job.status, error: job.error, started: job.started, created: job.created });
      if (job.status === "done" || job.status === "error") {
        stopPolling();
        if (job.status === "done") setLastResult({ kind: job.kind, result: job.result });
        refreshJobs();
        refreshArtifacts();
      }
    } catch { /* transient network error during poll */ }
  }, [stopPolling, refreshJobs, refreshArtifacts]);

  const submit = useCallback(async (kind: string, params: any) => {
    setLastResult(null);
    const { job_id } = await api.post<{ job_id: string }>("/jobs", { kind, params });
    setActiveJob({ id: job_id, kind, status: "pending" });
    stopPolling();
    timer.current = setInterval(() => tick(job_id), 1500);
    tick(job_id);
  }, [tick, stopPolling]);

  const loadJob = useCallback(async (id: string) => {
    const j = await api.get<Job>(`/jobs/${id}`);
    if (j.status === "done") setLastResult({ kind: j.kind, result: j.result });
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  return { status, jobs, activeJob, trace, logs, lastResult, artifacts, submit, stopPolling, loadJob, refreshArtifacts, refreshStatus };
}
