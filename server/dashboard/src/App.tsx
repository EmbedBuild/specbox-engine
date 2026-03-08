import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import ProjectDetail from './pages/ProjectDetail'
import Timeline from './pages/Timeline'
import Healing from './pages/Healing'
import E2ETesting from './pages/E2ETesting'
import Upgrades from './pages/Upgrades'
import SpecDriven from './pages/SpecDriven'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/project/:name" element={<ProjectDetail />} />
        <Route path="/project/:name/timeline" element={<Timeline />} />
        <Route path="/healing" element={<Healing />} />
        <Route path="/e2e" element={<E2ETesting />} />
        <Route path="/upgrades" element={<Upgrades />} />
        <Route path="/spec-driven" element={<SpecDriven />} />
      </Routes>
    </Layout>
  )
}
