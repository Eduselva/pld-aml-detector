import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import NewInvestigation from './pages/NewInvestigation'
import Report from './pages/Report'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/investigacoes/nova" element={<NewInvestigation />} />
        <Route path="/investigacoes/:id/relatorio" element={<Report />} />
      </Routes>
    </BrowserRouter>
  )
}
