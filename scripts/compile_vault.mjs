import fs from 'node:fs';
import path from 'node:path';
import solc from 'solc';

const contractPath = path.resolve('contracts/USYCVault_fixed.sol');
const source = fs.readFileSync(contractPath, 'utf8');

function findImports(importPath) {
  if (importPath.startsWith('@openzeppelin/contracts/')) {
    const fullPath = path.resolve('node_modules', importPath);
    if (fs.existsSync(fullPath)) {
      return { contents: fs.readFileSync(fullPath, 'utf8') };
    }
  }
  return { error: 'File not found: ' + importPath };
}

const input = {
  language: 'Solidity',
  sources: {
    'USYCVault_fixed.sol': {
      content: source,
    },
  },
  settings: {
    optimizer: {
      enabled: true,
      runs: 200,
    },
    outputSelection: {
      '*': {
        '*': ['abi', 'evm.bytecode', 'evm.deployedBytecode'],
      },
    },
  },
};

console.log('Compiling contracts/USYCVault_fixed.sol with solc...');
const output = JSON.parse(solc.compile(JSON.stringify(input), { import: findImports }));

let hasErrors = false;
if (output.errors) {
  for (const error of output.errors) {
    if (error.severity === 'error') {
      hasErrors = true;
      console.error('ERROR:', error.formattedMessage);
    } else {
      console.warn('WARN:', error.formattedMessage);
    }
  }
}

if (hasErrors) {
  console.error('Compilation failed!');
  process.exit(1);
}

const contract = output.contracts['USYCVault_fixed.sol']['USYCVaultFixed'];
const artifact = {
  contractName: 'USYCVaultFixed',
  abi: contract.abi,
  bytecode: '0x' + contract.evm.bytecode.object,
  deployedBytecode: '0x' + contract.evm.deployedBytecode.object,
};

const artifactDir = path.resolve('contracts/artifacts');
fs.mkdirSync(artifactDir, { recursive: true });
fs.writeFileSync(
  path.join(artifactDir, 'USYCVaultFixed.json'),
  JSON.stringify(artifact, null, 2)
);

console.log('Compilation SUCCESSFUL!');
console.log('Bytecode length:', artifact.bytecode.length);
console.log('ABI functions:', artifact.abi.filter(item => item.type === 'function').length);
console.log('Saved to contracts/artifacts/USYCVaultFixed.json');
