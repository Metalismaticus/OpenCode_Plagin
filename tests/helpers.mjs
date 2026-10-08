import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { Engine } from '../.opencode/studio/runtime/engine.mjs'

export const owner = { sessionID: 'ses-owner', agent: 'studio' }
export const coder = { sessionID: 'ses-code', agent: 'executor', parentID: owner.sessionID }
export const reviewer = { sessionID: 'ses-review', agent: 'reviewer', parentID: owner.sessionID }
export const words = 'Дерево должно реагировать на удар'

export function repo(test, options = {}) {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'studio-test-'))
  test.after(() => fs.rmSync(temporary, { recursive: true, force: true }))
  const root = path.join(temporary, 'Игра с пробелом')
  fs.mkdirSync(path.join(root, 'docs'), { recursive: true })
  fs.writeFileSync(path.join(root, 'docs/BATCH.md'), '# Текущая партия\n' + words)
  fs.writeFileSync(path.join(root, 'tree.js'), 'export const health = 10\n')
  fs.writeFileSync(path.join(root, 'other.js'), 'export const untouched = true\n')
  const git = (...args) => execFileSync('git', ['-C', root, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim()
  git('init', '-b', 'main'); git('config', 'user.name', 'Studio Test'); git('config', 'user.email', 'test@example.invalid')
  git('add', 'docs/BATCH.md', 'tree.js', 'other.js'); git('commit', '-m', 'Initial game')
  const engine = new Engine(root, options)
  const card = { id: 'batch-p1', batch: '2026-10-07', item: 1, step: 'implementation', kind: 'code', title: 'Реакция дерева', owner_words: words, goal: 'Понятная реакция', player_result: 'Прочность уменьшается', acceptance: ['Удар уменьшает прочность'], invariants: ['Остальные деревья целы'], out_of_scope: ['Падение'], sources: ['docs/BATCH.md'], references: [], skills: [], depends_on: [], files: ['tree.js'], checks: [{ name: 'parse', command: `"${process.execPath}" --check tree.js`, timeout_ms: 5000 }], how_to_see: 'Ударьте по дереву у спавна' }
  const report = { files: ['tree.js'], summary: 'Добавлена реакция', red_proof: 'Проверка до правки: прочность не меняется', checks: 'Проверка дерева зелёная', how_to_see: 'Ударьте по дереву у спавна', decisions: [], limitations: [] }
  const call = (action, data = {}, actor = owner) => engine.execute({ action, id: card.id, ...data }, actor)
  const start = async () => {
    await call('bind', { mode: 'development' })
    await call('create', { card })
    await call('begin', {}, coder)
    fs.writeFileSync(path.join(root, 'tree.js'), 'export const health = 9\n')
  }
  const submit = () => call('submit', { report }, coder)
  const approve = (actor = reviewer) => call('review', { verdict: 'APPROVED', spec: 'PASS', quality: 'PASS', criteria: ['tree.js: health becomes 9'], notes: [] }, actor)
  const checkpoint = async () => {
    git('add', 'tree.js'); git('commit', '-m', 'Пункт 1: дерево реагирует на удар')
    return call('checkpoint', { commit: git('rev-parse', 'HEAD') })
  }
  return { root, temporary, engine, git, card, report, call, start, submit, approve, checkpoint }
}
