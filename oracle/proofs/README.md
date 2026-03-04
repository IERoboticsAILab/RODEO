# Oracle Proofs Directory

This directory contains proof files (.bag files) that robots submit for task validation.

## Purpose

The `proofs/` directory serves as a **shared storage** between:
- **Host system**: Where robots place proof files
- **Oracle container**: Where the oracle reads and validates proofs

## Usage

### For Robots (Proof Submission)

When submitting a proof, save your .bag file here:
```
<location of this repo>/robotic_decentralized_organization/oracle/proofs/your_proof.bag
```

Then submit the proof URI:
```
file:///<location of this repo>/robotic_decentralized_organization/oracle/proofs/your_proof.bag
```

note: In the proofs directory there are two  examplaary proofs rosbags from task 1 (task_tid1_20250904_164349.bag) and task 10 (task_tid10_20250910_145742.bag).

❌ Task 1 is a failed task and will result in escrowed funds returend to creater.

✅ Task 2 is sucsesfull task and will result in escrowed funds relested to robot.

### For Oracle (Validation)

The oracle container has this directory mounted at the **same absolute path**, so file:// URIs resolve correctly.

## Example Files

- `task_tid1_20250904_164349.bag` - Sample delivery task proof
- `task_tid10_20250910_145742.bag` - Sample navigation task proof

## Best Practices

1. **Naming Convention**: Use format `task_tid{ID}_{timestamp}.bag`
2. **File Size**: Keep proof files reasonable (<100MB if possible)
3. **Cleanup**: Remove old proof files after validation (optional)
4. **Permissions**: Ensure oracle container has read access

## Notes

- This directory is mounted **read-only** in the container for security
- The oracle validates but never modifies proof files
- Original .bag files in parent directory are kept for reference
