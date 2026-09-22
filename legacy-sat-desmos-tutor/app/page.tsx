import SolverForm from "@/components/SolverForm";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center bg-slate-950 px-4 py-16 font-sans text-slate-100 sm:px-8">
      <main className="flex w-full max-w-2xl flex-col items-center gap-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            SAT Desmos Tutor
          </h1>
          <p className="mt-3 text-slate-400">
            Paste an SAT math problem. Get the fastest Desmos shortcut, not a
            page of algebra.
          </p>
        </div>
        <SolverForm />
      </main>
    </div>
  );
}
