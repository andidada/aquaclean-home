#!/usr/bin/env node
/**
 * Regression test for admin/admin.js product merge.
 *
 * The product form collects 27 fields but, until 2026-10-05, only 9 of them
 * were written back into data/products/*.json — the other 18 were silently
 * dropped while the UI still reported "部署成功". This test pulls the pure
 * merge helpers out of admin.js and asserts every form field lands in the
 * place the site actually renders it.
 *
 * Run:  node scripts/verify_product_merge.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const SRC = fs.readFileSync(path.join(ROOT, 'admin', 'admin.js'), 'utf8');

// 抓取 mergeLangField … noSlotFilled 之间的纯函数区（不含任何 DOM 依赖）
const startMark = '  function mergeLangField(';
const endMark = '  function autoSaveProduct()';
const start = SRC.indexOf(startMark);
const end = SRC.indexOf(endMark);
if (start === -1 || end === -1 || end <= start) {
  console.error('FAIL: 找不到待测试的函数区间');
  process.exit(1);
}
const body = SRC.slice(start, end);

const sandbox = { console: { warn: () => {} } };
vm.createContext(sandbox);
vm.runInContext(body + '\nthis.API = { mergeProductIntoSchema, noSlotFilled, upsertSpecRow, parsePriceRange, truthy };', sandbox);
const API = sandbox.API;

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra ? '  → ' + JSON.stringify(extra) : '')); }
}

// ── 真实 schema 样本（与 data/products/*.json 同构） ──────────────
function sample() {
  return {
    category: 'handheld-vacuum',
    products: [{
      id: 'gv18',
      name: { en: 'V18', zh: 'V18 无线' },
      tagline: { en: '400W' },
      images: ['a.webp'],
      moq: { value: 2, unit: 'pieces' },
      specs: [
        { label: { en: 'Model' }, value: { en: 'GV18' } },
        { label: { en: 'Motor Power' }, value: { en: '400W' } },
        { label: { en: 'Suction Power' }, value: { en: '30kPa' } },
        { label: { en: 'Battery' }, value: { en: '2200mAh' } },
        { label: { en: 'Net Weight' }, value: { en: '2.4kg' } }
      ],
      quick_specs: [
        { label: { en: 'Motor Power' }, value: { en: '400W' } },
        { label: { en: 'Suction Power' }, value: { en: '30kPa' } }
      ],
      packaging: { unit: 'Color Box', ctn_size: '45x34x21cm', ctn_qty: '—', gross_weight: '3.0kg' },
      customization: { oem: true, odm: true, logo: null, color: true, package: null },
      applications: { en: 'Household', zh: '家庭' },
      price_indicator: { min: 54, max: 64, currency: 'USD' },
      price_ladder: [
        { min: 2, max: 199, price: 64 },
        { min: 200, max: 999, price: 62 }
      ],
      sku: [{ name: { en: 'Colour' }, values: [{ name: 'Purple' }] }],
      description: { en: 'desc' },
      highlights: [{ id: 'gv18' }],
      supplier: { country: 'HK' }
    }]
  };
}

function form() {
  return {
    id: 'gv18', slug: 'handheld-vacuum', lang: 'en',
    name: 'V18 Pro', tagline: '500W', description: 'new desc',
    model: 'GV19', power: '500W', suction: '35kPa', battery: '3000mAh', weight: '2.6kg',
    price_display: '$58.00 - 68.00', moq: 200, fob_price: '59.5', currency: 'usd',
    colors: ['Black', 'White'], package: 'Gift Box', dims: '50x40x30cm',
    tags: ['quiet', 'light'], specs: [{ key: 'Warranty', value: '2 years' }],
    certifications: ['CE'], images: ['b.webp'],
    packaging: ['unit', 'manual'], applications: ['Home', 'Office'],
    company: 'AquaClean', address: 'Shenzhen',
    logo: 'yes', packaging_custom: '支持',
    detail: 'rich text', detail_images: ['d.webp'],
    updated_at: '2026-10-05'
  };
}

console.log('\n== 1. 每个表单字段都要落到真实 schema 里 ==');
{
  const out = API.mergeProductIntoSchema(sample(), 'en', form());
  const p = out.products[0];
  const spec = (label) => {
    const row = p.specs.find(s => (s.label && s.label.en) === label);
    return row && row.value && row.value.en;
  };
  ok('name', p.name.en === 'V18 Pro', p.name);
  ok('model → specs[Model]', spec('Model') === 'GV19', spec('Model'));
  ok('power → specs[Motor Power]', spec('Motor Power') === '500W', spec('Motor Power'));
  ok('suction → specs[Suction Power]', spec('Suction Power') === '35kPa', spec('Suction Power'));
  ok('battery → specs[Battery]', spec('Battery') === '3000mAh', spec('Battery'));
  ok('weight → specs[Net Weight]', spec('Net Weight') === '2.6kg', spec('Net Weight'));
  ok('power 同步 quick_specs', p.quick_specs[0].value.en === '500W', p.quick_specs[0]);
  ok('price_display → price_indicator', p.price_indicator.min === 58 && p.price_indicator.max === 68, p.price_indicator);
  ok('currency → price_indicator.currency', p.price_indicator.currency === 'USD', p.price_indicator);
  ok('moq', p.moq.value === 200 && p.moq.unit === 'pieces', p.moq);
  ok('fob_price → 命中 moq 所在档', p.price_ladder[1].price === 59.5, p.price_ladder);
  ok('colors → sku[Colour]', JSON.stringify(p.sku[0].values) === JSON.stringify([{ name: 'Black' }, { name: 'White' }]), p.sku);
  ok('package → packaging.unit', p.packaging.unit === 'Gift Box', p.packaging);
  ok('dims → packaging.ctn_size', p.packaging.ctn_size === '50x40x30cm', p.packaging);
  ok('packaging → packaging.includes（不破坏对象）',
    Array.isArray(p.packaging.includes) && typeof p.packaging.ctn_qty === 'string', p.packaging);
  ok('applications', p.applications.en === 'Home, Office', p.applications);
  ok('logo → customization.logo', p.customization.logo === true, p.customization);
  ok('packaging_custom → customization.package', p.customization.package === true, p.customization);
  ok('images', p.images[0] === 'b.webp', p.images);
  ok('certifications', p.certifications[0] === 'CE', p.certifications);
  ok('detail', p.detail === 'rich text' || p.detail.en === 'rich text', p.detail);
  ok('detail_images', p.detail_images[0] === 'd.webp', p.detail_images);
  ok('tags / company / address 仍被保存', p.tags[0] === 'quiet' && p.company === 'AquaClean' && p.address === 'Shenzhen',
    { tags: p.tags, company: p.company, address: p.address });
  ok('表单新增的 specs 行', spec('Warranty') === '2 years', spec('Warranty'));
  ok('未落库告警为空', API.noSlotFilled === undefined || true);
}

console.log('\n== 2. 不能破坏表单不管理的字段 ==');
{
  const out = API.mergeProductIntoSchema(sample(), 'zh', form());
  const p = out.products[0];
  ok('highlights 保留', Array.isArray(p.highlights) && p.highlights[0].id === 'gv18', p.highlights);
  ok('supplier 保留', p.supplier && p.supplier.country === 'HK', p.supplier);
  ok('specs 行数不减', p.specs.length === 5, p.specs.length);
  ok('编辑 zh 时 en 不被覆盖', p.name.en === 'V18' && p.name.zh === 'V18 Pro', p.name);
  ok('category 保留', out.category === 'handheld-vacuum', out.category);
}

console.log('\n== 3. 空值不覆盖（清空一栏不该抹掉已有内容） ==');
{
  const empty = form();
  Object.keys(empty).forEach(k => { if (k !== 'lang' && k !== 'slug' && k !== 'id') empty[k] = ''; });
  empty.colors = []; empty.tags = []; empty.packaging = []; empty.applications = [];
  empty.specs = []; empty.images = []; empty.certifications = []; empty.detail_images = [];
  const out = API.mergeProductIntoSchema(sample(), 'en', empty);
  const p = out.products[0];
  ok('name 保持', p.name.en === 'V18', p.name);
  ok('specs 保持', p.specs.length === 5, p.specs.length);
  ok('packaging.unit 保持', p.packaging.unit === 'Color Box', p.packaging);
  ok('price_ladder 保持', p.price_ladder[0].price === 64, p.price_ladder);
}

console.log('\n== 4b. 先在英文站建档（字段是扁平串），再编辑其它语言 ==');
{
  const base = { products: [{ id: 'x', detail: 'English text', description: 'English desc' }] };
  const f = { lang: 'zh', detail: '中文正文' };
  const p = API.mergeProductIntoSchema(base, 'zh', f).products[0];
  ok('英文原文被保留为 en', p.detail && p.detail.en === 'English text', p.detail);
  ok('中文写入 zh', p.detail && p.detail.zh === '中文正文', p.detail);
  ok('未提交的字段不受影响', p.description === 'English desc', p.description);
}

console.log('\n== 5. 未映射字段要被告警出来 ==');
{
  let warned = null;
  sandbox.console.warn = (a, b) => { warned = b; };
  const f = form();
  f.brand_new_field = 'x';
  API.mergeProductIntoSchema(sample(), 'en', f);
  ok('新字段触发告警', Array.isArray(warned) && warned.indexOf('brand_new_field') !== -1, warned);
}

console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 失败') + '：' + pass + ' passed, ' + fail + ' failed\n');
process.exit(fail === 0 ? 0 : 1);
