import { useEffect, useRef, useState } from 'react'

const POLL_INTERVAL_MS = 2000

const STATUS_LABELS = {
  queued:     'キュー待ち',
  processing: '生成中',
  done:       '完了',
  error:      'エラー',
}

export default function VideoPlayer({ jobId, onReset }) {
  const [job, setJob] = useState(null)
  const timerRef = useRef(null)

  const poll = async () => {
    try {
      const res = await fetch(`/jobs/${jobId}`)
      if (!res.ok) return
      const data = await res.json()
      setJob(data)
      if (data.status === 'done' || data.status === 'error') {
        clearInterval(timerRef.current)
      }
    } catch {
      // network error — keep polling
    }
  }

  useEffect(() => {
    poll()
    timerRef.current = setInterval(poll, POLL_INTERVAL_MS)
    return () => clearInterval(timerRef.current)
  }, [jobId])

  if (!job) {
    return (
      <div className="video-panel">
        <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>接続中...</p>
      </div>
    )
  }

  const videoUrl = `/videos/${jobId}`

  return (
    <div className="video-panel">
      {/* Header */}
      <div className="job-header">
        <span className="job-name">
          {job.params?.name ?? 'Plant'}
        </span>
        <button className="reset-btn" onClick={onReset}>
          別の植物を作る
        </button>
      </div>

      {/* Status badge */}
      <div>
        <span className={`status-badge ${job.status}`}>
          {job.status === 'processing' && <span className="spinner" />}
          {STATUS_LABELS[job.status] ?? job.status}
        </span>
      </div>

      {/* Progress bar (visible while processing or queued) */}
      {(job.status === 'processing' || job.status === 'queued') && (
        <div className="progress-area">
          <div className="progress-label">
            <span>フレーム生成中...</span>
            <span className="progress-pct">{job.progress ?? 0}%</span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${job.progress ?? 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Error */}
      {job.status === 'error' && (
        <div className="error-box">{job.error}</div>
      )}

      {/* Video */}
      {job.status === 'done' && (
        <>
          <div className="video-wrapper">
            <video
              key={jobId}
              src={videoUrl}
              controls
              autoPlay
              loop
              playsInline
            />
          </div>

          <a
            className="download-btn"
            href={videoUrl}
            download={`plant_${jobId.slice(0, 8)}.mp4`}
          >
            MP4 をダウンロード
          </a>

          {/* Params summary */}
          {job.params && <ParamsSummary params={job.params} />}
        </>
      )}
    </div>
  )
}

function ParamsSummary({ params }) {
  const ERA_NAMES = {
    hadean: 'ハデアン',
    archean: '太古代',
    proterozoic: '原生代',
    cambrian: 'カンブリア',
  }
  const PATTERN_NAMES = {
    tree: '樹木', bush: '低木', fern: 'シダ', moss: '苔', spiral: '螺旋',
  }
  return (
    <div style={{
      background: 'var(--surface2)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '12px',
      fontSize: '0.78rem',
      color: 'var(--text-dim)',
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: '4px 16px',
    }}>
      <span>形態: <b style={{ color: 'var(--text)' }}>{PATTERN_NAMES[params.growth_pattern]}</b></span>
      <span>時代: <b style={{ color: 'var(--text)' }}>{ERA_NAMES[params.era]}</b></span>
      <span>角度: <b style={{ color: 'var(--text)' }}>{params.branch_angle}°</b></span>
      <span>反復: <b style={{ color: 'var(--text)' }}>{params.iterations} iter</b></span>
      <span>CO₂: <b style={{ color: 'var(--text)' }}>{params.co2_level}×</b></span>
      <span>水分: <b style={{ color: 'var(--text)' }}>{params.moisture}</b></span>
    </div>
  )
}
