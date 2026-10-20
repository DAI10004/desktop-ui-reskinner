#!/usr/bin/env node
/*
 * asar_pack.js — desktop-ui-reskinner 的 ASAR 成员级操作后端 (ESM 动态加载版)
 *
 * 协议（给 reskin.py 解析）：
 *   调用方式： node asar_pack.js <action> [args...]
 *     action = list            <archive>
 *              extract-member  <archive> <member>            → 成员内容 base64 输出
 *              replace         <archive> <member> <srcFile>  → 解包→替换单成员→重打包→原子替换
 *
 *   stdout：每一行一个 JSON 对象（JSON Lines）。约定字段：
 *     {"event":"ready","asar_version":"..."}                       启动成功
 *     {"event":"list","members":["..."]}                           list 结果
 *     {"event":"member","name":"...","size":N,"data_b64":"..."}    extract-member 结果
 *     {"event":"replaced","member":"...","archive":"..."}         replace 完成
 *     {"event":"error","code":"MISSING_ASAR"|"MEMBER_NOT_FOUND"|"IO_ERROR"|"BAD_ARGS",
 *      "message":"...","install_hint":"..."}                       错误
 *   退出码：0 正常结束；2 依赖缺失/参数错误；1 其他运行时错误。
 *
 * 说明：@electron/asar v4 为 ESM-only，本脚本用动态 import() 加载其 lib/asar.js。
 * @electron/asar 查找顺序：
 *   1. 环境变量 RESKINNER_ASAR_DIR（指向含 @electron/asar 的 node_modules 根）
 *   2. 项目根 .tools/asar/node_modules（本脚本位于 <项目根>/desktop-ui-reskinner/scripts/）
 *   3. 全局解析（import('@electron/asar')）
 *   找不到时输出 MISSING_ASAR 与一键安装命令，绝不静默成功。
 */
'use strict';

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const __dirname = dirname(fileURLToPath(import.meta.url));

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

function fail(code, message, extra) {
  emit(Object.assign({ event: 'error', code: code, message: message }, extra || {}));
  process.exit(2);
}

async function resolveAsar() {
  const projectRoot = path.join(__dirname, '..', '..');
  const candidates = [];
  if (process.env.RESKINNER_ASAR_DIR) {
    candidates.push(process.env.RESKINNER_ASAR_DIR);
  }
  candidates.push(path.join(projectRoot, '.tools', 'asar', 'node_modules'));

  for (const c of candidates) {
    const entryJs = path.join(c, '@electron', 'asar', 'lib', 'asar.js');
    const pkgJson = path.join(c, '@electron', 'asar', 'package.json');
    if (fs.existsSync(entryJs)) {
      try {
        const mod = await import(pathToFileURL(entryJs).href);
        let version = 'unknown';
        try {
          version = JSON.parse(fs.readFileSync(pkgJson, 'utf8')).version;
        } catch (e) { /* 忽略 */ }
        return { mod, version, from: c };
      } catch (e) {
        // 继续尝试下一个候选
      }
    }
  }
  // 全局
  try {
    const mod = await import('@electron/asar');
    return { mod, version: 'global', from: 'global' };
  } catch (e) {
    fail('MISSING_ASAR',
      '未找到 @electron/asar（已尝试 RESKINNER_ASAR_DIR、.tools/asar、全局）',
      {
        install_hint:
          'cd ' + path.join(projectRoot, '.tools', 'asar') +
          ' && npm install @electron/asar --registry=https://registry.npmmirror.com'
      });
  }
}

const action = process.argv[2];
const archive = process.argv[3];

if (!action || !archive || !fs.existsSync(archive)) {
  fail('BAD_ARGS', '用法: node asar_pack.js <list|extract-member|replace> <archive> [member] [srcFile]');
}

const { mod: asar, version, from } = await resolveAsar();
emit({ event: 'ready', asar_version: version, loaded_from: from });

if (action === 'list') {
  try {
    const list = asar.listPackage(archive);
    emit({ event: 'list', members: Array.isArray(list) ? list : [] });
  } catch (e) {
    fail('IO_ERROR', 'listPackage 失败: ' + e.message);
  }
  process.exit(0);
}

if (action === 'extract-member') {
  const member = process.argv[4];
  if (!member) fail('BAD_ARGS', 'extract-member 需要 <member>');
  // @electron/asar v4 在 Windows 下内部用反斜杠存成员键; 同时尝试两种形式
  const candidates = [member, member.split('/').join('\\')];
  let buf, usedMember = null;
  for (const cand of candidates) {
    try {
      buf = asar.extractFile(archive, cand);
      usedMember = cand;
      break;
    } catch (e) { /* 尝试下一个 */ }
  }
  if (buf === undefined) {
    fail('MEMBER_NOT_FOUND', '成员不存在或读取失败: ' + member);
  }
  const b64 = Buffer.isBuffer(buf) ? buf.toString('base64') : Buffer.from(buf).toString('base64');
  emit({ event: 'member', name: usedMember, size: b64.length, data_b64: b64 });
  process.exit(0);
}

if (action === 'replace') {
  const member = process.argv[4];
  const srcFile = process.argv[5];
  if (!member || !srcFile) fail('BAD_ARGS', 'replace 需要 <member> <srcFile>');
  if (!fs.existsSync(srcFile)) fail('BAD_ARGS', '源文件不存在: ' + srcFile);

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'reskin-asar-'));
  const tmpAsar = path.join(os.tmpdir(), 'reskin-asar-' + process.pid + '.new.asar');
  try {
    asar.extractAll(archive, tmpDir);
    const memberPath = path.join(tmpDir, member.split('/').join(path.sep));
    fs.mkdirSync(path.dirname(memberPath), { recursive: true });
    fs.copyFileSync(srcFile, memberPath);
    await asar.createPackage(tmpDir, tmpAsar);
    const staged = archive + '.tmp-replace';
    fs.copyFileSync(tmpAsar, staged);
    fs.renameSync(staged, archive);
    emit({ event: 'replaced', member: member, archive: archive });
  } catch (e) {
    try { fs.unlinkSync(archive + '.tmp-replace'); } catch (_) {}
    fail('IO_ERROR', 'replace 失败: ' + e.message);
  } finally {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch (_) {}
    try { fs.unlinkSync(tmpAsar); } catch (_) {}
  }
  process.exit(0);
}

fail('BAD_ARGS', '未知 action: ' + action);
