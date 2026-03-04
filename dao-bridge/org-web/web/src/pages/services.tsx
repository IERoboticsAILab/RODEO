// src/pages/services.tsx
import { useState } from "react";
import Shell from "../components/Shell";
import { CreateServiceForm } from "../components/Forms";
import ServiceTable from "../components/ServiceTable";
import { createService, deleteService, fetchServices, activateService, setServiceBusy } from "../lib/api";
import useSWR from "swr";

export default function ServicesPage() {
  const { data, mutate } = useSWR("services", fetchServices, { refreshInterval: 3000 });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [serviceType, setServiceType] = useState("");
  const [price, setPrice] = useState(0);

  async function handleCreate(_: any) {
    const payload = {
      name,
      description,
      category,
      serviceType,
      priceIec: price,
    };
    await createService(payload);
    await mutate();
    setName("");
    setDescription("");
    setCategory("");
    setServiceType("");
    setPrice(0);
  }

  async function handleAction(
  id: number | string,
  action: "remove" | "activate" | "busy-on" | "busy-off"
) {
  const sid = Number(id);
  if (action === "remove") {
    await deleteService(sid);
  } else if (action === "activate") {
    await activateService(sid);
  } else if (action === "busy-on") {
    await setServiceBusy(sid, true);
  } else if (action === "busy-off") {
    await setServiceBusy(sid, false);
  }
  await mutate();
}

  return (
    <Shell>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Services</h1>
      </div>
      <div className="grid grid-cols-1 gap-4">
        <div className="card p-4">
          <CreateServiceForm
            onCreate={handleCreate}
            setName={setName}
            setDescription={setDescription}
            setCategory={setCategory}
            setServiceType={setServiceType}
            setPrice={setPrice}
            name={name}
            description={description}
            category={category}
            serviceType={serviceType}
            price={price}
          />
        </div>
        
          <section className="space-y-2">
            <h2 className="font-semibold">Created by this organization</h2>
            <ServiceTable rows={data?.mine ?? []} onAction={handleAction} />
          </section>
        </div>
    </Shell>
  );
}
