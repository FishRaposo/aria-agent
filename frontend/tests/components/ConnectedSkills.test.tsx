import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SkillsView from "@/components/SkillsView";
import { setProviderMode } from "@/lib/demo-scenarios";
const snapshot = { session_id:"default", run_id:"second", context_available:true, catalog:[{name:"calculator",description:"Numeric tools",scope:"builtin",source:"builtin/calculator"}], activated:[{name:"calculator",scope:"builtin",source:"builtin/calculator",run_id:"second",loaded:true,instructions:"Immutable recorded instructions",selection_method:"automatic",selection_reason:"Matched calculator tool intent",content_hash:"sha256:recorded"}], context_report:{visible_skill_count:1,eager_hints_used:false,loaded_instruction_bodies:[],provider:"keyword",source_scopes:["builtin"],context_consumed:false} };
beforeEach(() => { setProviderMode("connected"); global.fetch = vi.fn(async (url) => ({ok:true,json:async()=>String(url).includes("/agent/runs")?{runs:[{id:"first",query:"First request"},{id:"second",query:"Second request"}]}:snapshot})) as unknown as typeof fetch; });
afterEach(() => {cleanup();vi.restoreAllMocks();});
describe("connected saved skill evidence",()=>{
 it("lets the reader inspect a selected historical run and explains actual loading",async()=>{
  render(<SkillsView/>);
  const selector=await screen.findByLabelText("Skill evidence run");
  fireEvent.change(selector,{target:{value:"first"}});
  await waitFor(()=>expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("run_id=first"),expect.anything()));
  expect(screen.getByText(/Matched calculator tool intent/)).toBeInTheDocument();
  expect(screen.getByText(/not consumed by a model/i)).toBeInTheDocument();
  expect(screen.getByText("Immutable recorded instructions")).toBeInTheDocument();
  expect(screen.getByText("sha256:recorded")).toBeInTheDocument();
 });
 it("marks legacy runs as unavailable rather than inventing instruction evidence",async()=>{
  global.fetch=vi.fn(async(url)=>({ok:true,json:async()=>String(url).includes("/agent/runs")?{runs:[]}:{...snapshot,activated:[],context_available:false}})) as unknown as typeof fetch;
  render(<SkillsView/>);
  expect(await screen.findByText(/No recorded skill evidence/i)).toBeInTheDocument();
 });
});
