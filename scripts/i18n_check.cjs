#!/usr/bin/env node
/**
 * v2.21: i18n 残余字符串扫描器
 *
 * 扫描 frontend/src 下的 ts/tsx 文件，查找 **未经 t() 包裹** 的 CJK 字符串字面量，
 * 便于 CI 中阻止新增硬编码 zh-CN 文案。
 *
 * 规则：
 * - 只看字符串字面量："..."、'...'、`...`（反引号只考虑无 ${} 的简单情况）。
 * - 字面量包含 CJK 字符（\u4e00-\u9fff） → 候选。
 * - 若该字面量所在的行（或上一行结尾）出现 `t(`、`t<`、`i18n.t(`、`useTranslation` 上下文 → 视为已 i18n。
 * - 若字面量所在行含 `// i18n-ignore` 行尾注释 → 忽略。
 * - 文件在 ALLOWLIST 中 → 跳过。
 *
 * 退出码：0 = 无残余；1 = 存在残余。
 * 环境变量 `I18N_BASELINE=<n>` 可容忍不超过 n 条（用于渐进收敛）。
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', 'frontend', 'src');
const ALLOWLIST = [
  // 翻译字典本身
  path.join('frontend', 'src', 'i18n.ts'),
];

const CJK = /[\u4e00-\u9fff]/;
const STRING_LITERAL = /(?<!\\)(["'`])((?:\\.|(?!\1)[^\\])*)\1/g;

function walk(dir, acc = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) walk(full, acc);
    else if (/\.(ts|tsx)$/.test(name)) acc.push(full);
  }
  return acc;
}

function isAllowed(relPath) {
  return ALLOWLIST.some((a) => relPath.endsWith(a));
}

function scanFile(file) {
  const rel = path.relative(path.resolve(__dirname, '..'), file);
  if (isAllowed(rel)) return [];
  const text = fs.readFileSync(file, 'utf8');
  const lines = text.split(/\r?\n/);
  const findings = [];

  // 预生成 per-line 标记：是否在 // i18n-ignore 行
  const ignoreLines = new Set();
  lines.forEach((ln, i) => {
    if (/i18n-ignore/.test(ln)) ignoreLines.add(i);
  });

  // 粗略剥离块注释以减少误报
  const stripped = text.replace(/\/\*[\s\S]*?\*\//g, (m) => ' '.repeat(m.length));

  let m;
  while ((m = STRING_LITERAL.exec(stripped)) !== null) {
    const literal = m[0];
    const inner = m[2];
    if (!CJK.test(inner)) continue;
    const idx = m.index;
    // 行号
    let line = 0;
    let acc = 0;
    for (let i = 0; i < lines.length; i++) {
      if (acc + lines[i].length >= idx) { line = i; break; }
      acc += lines[i].length + 1;
    }
    if (ignoreLines.has(line)) continue;
    const lineText = lines[line] || '';
    // 行注释剥除后判断
    const codePart = lineText.replace(/\/\/.*$/, '');
    if (!codePart.includes(literal.slice(0, 8)) && !codePart.includes(inner.slice(0, 8))) {
      // 字面量出现在注释里 → 忽略
      continue;
    }
    // t() 包裹启发式
    const wrappedCtx = /(?:\b|^)(?:t|i18n\.t)\s*[<(]/;
    const prev = line > 0 ? lines[line - 1] : '';
    if (wrappedCtx.test(lineText) || wrappedCtx.test(prev)) continue;
    findings.push({ file: rel, line: line + 1, text: inner.length > 60 ? inner.slice(0, 57) + '...' : inner });
  }
  return findings;
}

function main() {
  if (!fs.existsSync(ROOT)) {
    console.error(`[i18n-check] 未找到 ${ROOT}`);
    process.exit(2);
  }
  const files = walk(ROOT);
  const all = [];
  for (const f of files) {
    all.push(...scanFile(f));
  }
  const baseline = parseInt(process.env.I18N_BASELINE || '0', 10);
  if (all.length === 0) {
    console.log('[i18n-check] ✅ 未发现未 i18n 的 CJK 字符串');
    process.exit(0);
  }
  console.log(`[i18n-check] ⚠ 发现 ${all.length} 条未 i18n 的 CJK 字符串 (baseline=${baseline})：`);
  for (const f of all.slice(0, 200)) {
    console.log(`  ${f.file}:${f.line}  "${f.text}"`);
  }
  if (all.length > 200) {
    console.log(`  ... 及其余 ${all.length - 200} 条`);
  }
  if (all.length <= baseline) {
    console.log('[i18n-check] 在 baseline 容忍范围内，通过。');
    process.exit(0);
  }
  process.exit(1);
}

main();
