import { useState } from 'react'

const GROWTH_PATTERNS = [
  { value: 'tree',   label: '樹木' },
  { value: 'bush',   label: '低木' },
  { value: 'fern',   label: 'シダ' },
  { value: 'moss',   label: '苔'   },
  { value: 'spiral', label: '螺旋' },
]

const ERAS = [
  { value: 'hadean',       name: 'ハデアン',   desc: '46-40億年前 · 灼熱の溶岩大地' },
  { value: 'archean',      name: '太古代',     desc: '40-25億年前 · メタン大気' },
  { value: 'proterozoic',  name: '原生代',     desc: '25-5.4億年前 · 酸素蓄積' },
  { value: 'cambrian',     name: 'カンブリア', desc: '5.4億年前 · 生命爆発' },
]

const colorToHex = ([r, g, b]) =>
  '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')

const hexToColor = (hex) => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
]

const DEFAULT_PARAMS = {
  name: '謎の原始植物',
  description: '',
  growth_pattern: 'fern',
  branch_angle: 25,
  iterations: 4,
  stem_color: [90, 55, 20],
  leaf_color: [25, 130, 50],
  era: 'archean',
  co2_level: 10,
  uv_intensity: 0.8,
  moisture: 0.5,
  temperature: 40,
  duration: 10,
  fps: 24,
}

function Slider({ label, value, min, max, step = 1, unit = '', onChange }) {
  return (
    <div className="field">
      <label>{label}</label>
      <div className="slider-row">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <span className="slider-value">{value}{unit}</span>
      </div>
    </div>
  )
}

export default function PlantForm({ onJobCreated }) {
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [loading, setLoading] = useState(false)

  const set = (key, val) => setParams((p) => ({ ...p, [key]: val }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await fetch('/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(JSON.stringify(err))
      }
      const data = await res.json()
      onJobCreated(data.job_id)
    } catch (err) {
      alert('エラー: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      {/* ---- 基本情報 ---- */}
      <section className="form-section">
        <div className="section-title">植物の基本情報</div>

        <div className="field">
          <label>植物の名前</label>
          <input
            type="text"
            value={params.name}
            onChange={(e) => set('name', e.target.value)}
            placeholder="例: クリムゾンシダ"
          />
        </div>

        <div className="field">
          <label>説明（任意）</label>
          <textarea
            value={params.description}
            onChange={(e) => set('description', e.target.value)}
            placeholder="例: 胞子で繁殖し、紫外線に強い古代シダ植物"
          />
        </div>
      </section>

      {/* ---- 成長形態 ---- */}
      <section className="form-section">
        <div className="section-title">成長パターン</div>

        <div className="field">
          <label>形態</label>
          <div className="pattern-row">
            {GROWTH_PATTERNS.map((p) => (
              <button
                key={p.value}
                type="button"
                className={`pattern-btn${params.growth_pattern === p.value ? ' selected' : ''}`}
                onClick={() => set('growth_pattern', p.value)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <Slider
          label="枝分かれ角度"
          value={params.branch_angle}
          min={5} max={60} step={1} unit="°"
          onChange={(v) => set('branch_angle', v)}
        />

        <Slider
          label="成長段階（反復回数）"
          value={params.iterations}
          min={1} max={6} step={1} unit=" iter"
          onChange={(v) => set('iterations', v)}
        />
      </section>

      {/* ---- 色 ---- */}
      <section className="form-section">
        <div className="section-title">色彩</div>
        <div className="color-row">
          <div className="color-field">
            <label>茎・幹の色</label>
            <input
              type="color"
              value={colorToHex(params.stem_color)}
              onChange={(e) => set('stem_color', hexToColor(e.target.value))}
            />
          </div>
          <div className="color-field">
            <label>葉の色</label>
            <input
              type="color"
              value={colorToHex(params.leaf_color)}
              onChange={(e) => set('leaf_color', hexToColor(e.target.value))}
            />
          </div>
        </div>
      </section>

      {/* ---- 地球環境 ---- */}
      <section className="form-section">
        <div className="section-title">原始地球の環境</div>

        <div className="field">
          <label>地質時代</label>
          <div className="era-grid">
            {ERAS.map((era) => (
              <div
                key={era.value}
                className={`era-card${params.era === era.value ? ' selected' : ''}`}
                onClick={() => set('era', era.value)}
              >
                <div className="era-name">{era.name}</div>
                <div className="era-desc">{era.desc}</div>
              </div>
            ))}
          </div>
        </div>

        <Slider
          label="CO₂濃度（現代比）"
          value={params.co2_level}
          min={1} max={100} step={1} unit="×"
          onChange={(v) => set('co2_level', v)}
        />

        <Slider
          label="紫外線強度"
          value={params.uv_intensity}
          min={0} max={1} step={0.05} unit=""
          onChange={(v) => set('uv_intensity', v)}
        />

        <Slider
          label="水分量"
          value={params.moisture}
          min={0} max={1} step={0.05} unit=""
          onChange={(v) => set('moisture', v)}
        />

        <Slider
          label="気温"
          value={params.temperature}
          min={0} max={80} step={1} unit="°C"
          onChange={(v) => set('temperature', v)}
        />
      </section>

      {/* ---- 動画設定 ---- */}
      <section className="form-section">
        <div className="section-title">動画設定</div>

        <Slider
          label="動画の長さ"
          value={params.duration}
          min={5} max={30} step={1} unit=" 秒"
          onChange={(v) => set('duration', v)}
        />

        <div className="field">
          <label>フレームレート</label>
          <select value={params.fps} onChange={(e) => set('fps', Number(e.target.value))}>
            <option value={12}>12 fps（軽量）</option>
            <option value={24}>24 fps（標準）</option>
            <option value={30}>30 fps（高品質）</option>
          </select>
        </div>
      </section>

      <button type="submit" className="submit-btn" disabled={loading}>
        {loading ? '送信中...' : 'シミュレーション開始'}
      </button>
    </form>
  )
}
