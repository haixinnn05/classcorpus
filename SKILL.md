---
name: classcorpus
description: Use this skill to index or search local lecture folders containing PDF or PowerPoint files and answer with exact citations.
---

# ClassCorpus

## Overview

ClassCorpus gives an agent a local, reusable index of course materials instead
of rereading lecture files for every request.

Use it when the user wants to sync a lecture folder, search indexed course
content, or answer study questions with slide- or page-level citations.

## Core Workflow

1. Index or refresh a local course directory that contains `.pdf` or `.pptx`
   lecture materials.
2. Search the local index before answering course-specific questions.
3. Return the smallest relevant set of cited records instead of loading an
   entire semester into context.
4. Keep generated data in the local ClassCorpus data directory and never modify
   source lecture files.

## When To Use

- The user wants to register or refresh a course folder on disk.
- The user asks about content that should be grounded in lecture PDFs or
  PowerPoint decks.
- The user wants cited summaries, comparisons, flashcards, or study materials
  derived from indexed lectures.
- The user wants visual slide analysis to remain local and agent-native.

## Guardrails

- Never modify or delete lecture source files.
- Prefer exact citations over uncited summaries.
- Keep generated data outside lecture folders and respect
  `CLASSCORPUS_DATA_DIR` when it is set.
- Treat visual analysis as opt-in work performed by the active agent.
