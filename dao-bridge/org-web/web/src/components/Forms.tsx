// src/components/Forms.tsx

type TaskFormProps = {
  onCreate: (args: { title: string; description: string; reward: number }) => Promise<void> | void;
  setTitle: (v: string) => void;
  setDescription: (v: string) => void;
  setCategory: (v: string) => void;
  setType: (v: string) => void;
  setReward: (v: number) => void;
  title: string;
  description: string;
  category: string;
  type: string;
  reward: number;
};

export function CreateTaskForm({
  onCreate,
  setTitle,
  setDescription,
  setCategory,
  setType,
  setReward,
  title,
  description,
  category,
  type,
  reward,
}: TaskFormProps) {
  return (
    <form
      onSubmit={async e => {
        e.preventDefault();
        await onCreate({ title, description, reward });
        setTitle("");
        setDescription("");
        setCategory("");
        setType("");
        setReward(100);
      }}
className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end"
    >
      <div className="space-y-1 md:col-span-2">
        <label className="label">Title</label>
        <input
          className="input focus-ring"
          value={title}
          onChange={e => setTitle(e.target.value)}
          required
        />
      </div>

      {/* Use a text input here to keep height compact for a single row */}
      <div className="space-y-1 md:col-span-4">
        <label className="label">Description</label>
        <input
          className="input focus-ring"
          value={description}
          onChange={e => setDescription(e.target.value)}
        />
      </div>

      <div className="space-y-1 md:col-span-2">
        <label className="label">Category</label>
        <input
          className="input focus-ring"
          value={category}
          onChange={e => setCategory(e.target.value)}
        />
      </div>

      <div className="space-y-1 md:col-span-2">
        <label className="label">Type</label>
        <input
          className="input focus-ring"
          value={type}
          onChange={e => setType(e.target.value)}
        />
      </div>

      <div className="space-y-1 md:col-span-1">
        <label className="label">Reward</label>
        <input
          type="number"
          className="input focus-ring"
          value={reward}
          onChange={e => setReward(Number(e.target.value))}
          min={1}
          required
        />
      </div>

      <div className="md:col-span-1 flex md:block">
        <button className="btn btn-default focus-ring w-full md:w-auto" type="submit">
          Create task
        </button>
      </div>
    </form>
  );
}

type ServiceFormProps = {
  onCreate: (args: { name: string; price: number; category: string; serviceType: string }) => Promise<void> | void;
  setName: (v: string) => void;
  setDescription: (v: string) => void;
  setCategory: (v: string) => void;
  setServiceType: (v: string) => void;
  setPrice: (v: number) => void;
  name: string;
  description: string;
  category: string;
  serviceType: string;
  price: number;
};

export function CreateServiceForm({
  onCreate,
  setName,
  setDescription,
  setCategory,
  setServiceType,
  setPrice,
  name,
  description,
  category,
  serviceType,
  price,
}: ServiceFormProps) {
  return (
    <form
      onSubmit={async e => {
        e.preventDefault();
        await onCreate({ name, price, category, serviceType });
        setName("");
        setDescription("");
        setCategory("");
        setServiceType("");
        setPrice(0);
      }}
      className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end"
    >
      <div className="space-y-1 md:col-span-2">
        <label className="label">Name</label>
        <input className="input focus-ring" value={name} onChange={e => setName(e.target.value)} required />
      </div>

      {/* Use input to keep a single row, like tasks */}
      <div className="space-y-1 md:col-span-4">
        <label className="label">Description</label>
        <input className="input focus-ring" value={description} onChange={e => setDescription(e.target.value)} />
      </div>

      <div className="space-y-1 md:col-span-2">
        <label className="label">Category</label>
        <input className="input focus-ring" value={category} onChange={e => setCategory(e.target.value)} />
      </div>

      <div className="space-y-1 md:col-span-2">
        <label className="label">Type</label>
        <input className="input focus-ring" value={serviceType} onChange={e => setServiceType(e.target.value)} />
      </div>

      <div className="space-y-1 md:col-span-1">
        <label className="label">Price</label>
        <input type="number" className="input focus-ring" value={price} onChange={e => setPrice(Number(e.target.value))} min={0} />
      </div>

      <div className="md:col-span-1 flex md:block">
        <button className="btn btn-default focus-ring w-full md:w-auto" type="submit">
          Create service
        </button>
      </div>
    </form>
  );
}
