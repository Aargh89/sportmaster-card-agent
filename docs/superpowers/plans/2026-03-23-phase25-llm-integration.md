# Phase 2.5: Real LLM Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace stub/template-based agent logic with CrewAI Agent+Task execution using real LLMs via OpenRouter, while keeping all existing tests passing via a test-mode bypass.

**Architecture:** Each agent class gets a `run_with_crew()` method that creates a CrewAI Agent + Task, executes via Crew, and parses structured output. The existing rule-based methods remain as fallback (test mode). Environment variable `OPENROUTER_API_KEY` controls whether real LLM or stub is used.

**Tech Stack:** CrewAI 1.5 (Agent, Task, Crew), OpenRouter API, Pydantic structured output

---

## Design Decision: Dual-Mode Agents

Each agent supports two modes:
1. **Stub mode** (default, for tests): existing rule-based logic — no API calls
2. **LLM mode** (when `OPENROUTER_API_KEY` set): CrewAI Agent+Task with real prompts

This is achieved by a simple check in each agent's main method.

---
