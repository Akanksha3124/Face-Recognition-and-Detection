// Phase 1: skeleton shell only.
// Routing (React Router), auth context, and TanStack Query provider
// are wired in during Phase 5 (frontend authentication + dashboard).
function App() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-slate-800">
          Person Identification Platform
        </h1>
        <p className="text-slate-500 mt-2">Frontend skeleton — Phase 1</p>
      </div>
    </div>
  );
}

export default App;
