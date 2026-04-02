import { useState } from 'react'
import PlantForm from './components/PlantForm'
import VideoPlayer from './components/VideoPlayer'

export default function App() {
  const [jobId, setJobId] = useState(null)

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <h1 className="title">Plant Genesis Simulator</h1>
          <p className="subtitle">原始の地球に架空の植物を生やす</p>
        </div>
      </header>

      <main className="main">
        <div className="panel panel-left">
          <PlantForm
            onJobCreated={(id) => setJobId(id)}
          />
        </div>

        <div className="panel panel-right">
          {jobId ? (
            <VideoPlayer jobId={jobId} onReset={() => setJobId(null)} />
          ) : (
            <div className="empty-state">
              <div className="empty-icon">🌿</div>
              <p>左のフォームから植物を設定し、</p>
              <p>シミュレーションを開始してください</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
